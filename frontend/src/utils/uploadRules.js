// Same rules as the backend (app/services/file_validation.py, MAX_UPLOAD_MB).
// Checked in the browser for instant feedback – the server checks everything again.

export const MAX_UPLOAD_MB = 25;
export const ALLOWED_EXTENSIONS = [
  'pdf',
  'docx',
  'xlsx',
  'pptx',
  'txt',
  'csv',
  'png',
  'jpg',
  'jpeg',
];
export const ALLOWED_TEXT = 'PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG';

/** Returns an error message, or null if the file looks fine. */
export function precheck(file) {
  const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : '';
  if (!ALLOWED_EXTENSIONS.includes(extension)) return 'This file type is not allowed.';
  if (file.size === 0) return 'The file is empty.';
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `File exceeds the ${MAX_UPLOAD_MB} MB limit.`;
  return null;
}
