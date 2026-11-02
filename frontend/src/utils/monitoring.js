// Shared by the Milestone 3 admin pages.

export const FILE_TYPES = ['document', 'spreadsheet', 'presentation', 'image', 'text', 'other'];
export const ACTIVITY_TYPES = [
  'login',
  'logout',
  'upload',
  'download',
  'access',
  'share',
  'link_access',
  'unauthorized',
  'file_management',
  'vault',
  'account',
  'admin',
];

/** 'link_access' → 'Link access' */
export function humanize(key) {
  return key.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase());
}
