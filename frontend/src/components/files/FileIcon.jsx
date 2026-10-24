import { fileIcon } from '../../utils/format';

const SIZES = {
  sm: 'size-8 rounded-lg [&>svg]:size-4',
  md: 'size-9 rounded-lg [&>svg]:size-[18px]',
  lg: 'size-14 rounded-2xl [&>svg]:size-7',
};

/** A file-type tile: coloured square with the type icon (PDF red, sheet green, image violet …). */
export default function FileIcon({ category, size = 'md' }) {
  const { Icon, tile } = fileIcon(category);
  return (
    <span className={`grid shrink-0 place-items-center ring-1 ring-inset ${tile} ${SIZES[size]}`}>
      <Icon aria-hidden="true" />
    </span>
  );
}
