import { ChevronRight, Folder, Home } from 'lucide-react';
import { useEffect, useState } from 'react';

import { getErrorMessage } from '../api/client';
import { getFolder, listFolders } from '../api/files';
import Button from './Button';
import Modal from './Modal';

/**
 * Lets the user browse folders and pick a destination.
 * excludeId: a folder being moved can't be opened/chosen as its own destination.
 */
export default function MoveDialog({ itemName, excludeId, onMove, onClose }) {
  const [location, setLocation] = useState(null); // null = top level ("My Files")
  const [crumbs, setCrumbs] = useState([]);
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [moving, setMoving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listFolders({ parentId: location }),
      location ? getFolder(location) : Promise.resolve(null),
    ])
      .then(([children, detail]) => {
        if (cancelled) return;
        setFolders(children.filter((f) => f.id !== excludeId));
        setCrumbs(detail ? detail.breadcrumbs : []);
        setLoading(false);
      })
      .catch((err) => !cancelled && setError(getErrorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [location, excludeId]);

  function open(folderId) {
    setLoading(true);
    setLocation(folderId);
  }

  async function handleMove() {
    setMoving(true);
    setError('');
    try {
      await onMove(location);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
      setMoving(false);
    }
  }

  return (
    <Modal title={`Move “${itemName}”`} onClose={onClose}>
      <nav className="flex flex-wrap items-center gap-1 text-sm" aria-label="Destination">
        <button
          type="button"
          onClick={() => open(null)}
          className="flex items-center gap-1 rounded px-1 text-blue-600 hover:underline"
        >
          <Home className="size-4" /> My Files
        </button>
        {crumbs.map((crumb) => (
          <span key={crumb.id} className="flex items-center gap-1">
            <ChevronRight className="size-4 text-slate-400" />
            <button
              type="button"
              onClick={() => open(crumb.id)}
              className="rounded px-1 text-blue-600 hover:underline"
            >
              {crumb.name}
            </button>
          </span>
        ))}
      </nav>

      <ul className="mt-3 h-56 overflow-y-auto rounded-lg border border-slate-200">
        {loading ? (
          <li className="p-4 text-sm text-slate-400">Loading…</li>
        ) : folders.length === 0 ? (
          <li className="p-4 text-sm text-slate-400">No folders here</li>
        ) : (
          folders.map((folder) => (
            <li key={folder.id}>
              <button
                type="button"
                onClick={() => open(folder.id)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <Folder className="size-4 text-blue-500" aria-hidden="true" />
                {folder.name}
              </button>
            </li>
          ))
        )}
      </ul>

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button loading={moving} onClick={handleMove}>
          Move here
        </Button>
      </div>
    </Modal>
  );
}
