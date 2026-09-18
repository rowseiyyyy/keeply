const path = require('path');
const fs = require('fs');
const express = require('express');
const multer = require('multer');
const { v4: uuid } = require('uuid');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth);

const UPLOAD_DIR = path.join(__dirname, '..', '..', 'uploads');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname || '');
    cb(null, `${uuid()}${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: Number(process.env.MAX_UPLOAD_BYTES) || 15 * 1024 * 1024 },
});

// POST /api/uploads  (multipart/form-data, field name "file")
// Returns metadata the frontend can store directly on a note's images/attachments array,
// replacing the old approach of embedding a base64 dataUrl in localStorage.
router.post('/', upload.single('file'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file provided (expected field "file")' });
  const id = path.parse(req.file.filename).name;
  res.status(201).json({
    id,
    name: req.file.originalname,
    size: req.file.size,
    type: req.file.mimetype,
    url: `/uploads/${req.file.filename}`,
  });
});

module.exports = router;
