import { useState } from 'react';

import { getErrorMessage } from '../api/client';
import Button from './Button';
import FormField from './FormField';
import Modal from './Modal';

/** Asks for a name (new folder, rename). `onSubmit` may throw; the error is shown in the dialog. */
export default function NameDialog({
  title,
  label,
  initialValue = '',
  submitLabel,
  onSubmit,
  onClose,
}) {
  const [name, setName] = useState(initialValue);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setSaving(true);
    try {
      await onSubmit(name.trim());
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
      setSaving(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormField
          label={label}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          onFocus={(e) => {
            // Select the name without the extension, like a desktop file manager.
            const dot = e.target.value.lastIndexOf('.');
            e.target.setSelectionRange(0, dot > 0 ? dot : e.target.value.length);
          }}
          required
        />
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving} disabled={!name.trim()}>
            {submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
