import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ReactNode } from 'react'
import type { FileItem } from '../fileItems'

interface Props {
  items: FileItem[]
  onChange: (items: FileItem[]) => void
  renderPreview?: (item: FileItem) => ReactNode
  disabled?: boolean
}

export default function SortableFileList({ items, onChange, renderPreview, disabled }: Props) {
  const sensors = useSensors(
    // A small drag threshold lets clicks on the remove button through.
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return
    const from = items.findIndex((i) => i.id === active.id)
    const to = items.findIndex((i) => i.id === over.id)
    onChange(arrayMove(items, from, to))
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={items} strategy={rectSortingStrategy} disabled={disabled}>
        <ol className="file-grid">
          {items.map((item, index) => (
            <SortableFile
              key={item.id}
              item={item}
              index={index}
              preview={renderPreview?.(item)}
              disabled={disabled}
              onRemove={() => onChange(items.filter((i) => i.id !== item.id))}
            />
          ))}
        </ol>
      </SortableContext>
    </DndContext>
  )
}

interface SortableFileProps {
  item: FileItem
  index: number
  preview?: ReactNode
  disabled?: boolean
  onRemove: () => void
}

function SortableFile({ item, index, preview, disabled, onRemove }: SortableFileProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })

  return (
    <li
      ref={setNodeRef}
      className={`file-card${isDragging ? ' file-card-dragging' : ''}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
    >
      <span className="file-index">{index + 1}</span>
      {!disabled && (
        <button
          type="button"
          className="file-remove"
          aria-label={`Remove ${item.file.name}`}
          onClick={onRemove}
          onKeyDown={(e) => e.stopPropagation()}
        >
          ×
        </button>
      )}
      <div className="file-preview">{preview ?? <span className="file-badge">PDF</span>}</div>
      <div className="file-card-name" title={item.file.name}>
        {item.file.name}
      </div>
    </li>
  )
}
