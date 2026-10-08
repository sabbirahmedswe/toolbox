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
import { useState, type ReactNode } from 'react'
import type { FileItem } from '../fileItems'
import { FileCardBody } from './FileCard'

interface Props {
  items: FileItem[]
  onChange: (items: FileItem[]) => void
  renderPreview?: (item: FileItem) => ReactNode
  /** Adds a zoom button to each card; renders the enlarged view, which calls `onClose` when dismissed. */
  renderZoom?: (item: FileItem, onClose: () => void) => ReactNode
  disabled?: boolean
}

export default function SortableFileList({ items, onChange, renderPreview, renderZoom, disabled }: Props) {
  const [zoomedId, setZoomedId] = useState<string | null>(null)
  const zoomed = items.find((i) => i.id === zoomedId)

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
          {items.map((item) => (
            <SortableFile
              key={item.id}
              item={item}
              preview={renderPreview?.(item)}
              disabled={disabled}
              onZoom={renderZoom && (() => setZoomedId(item.id))}
              onRemove={() => onChange(items.filter((i) => i.id !== item.id))}
            />
          ))}
        </ol>
      </SortableContext>
      {/* Outside the cards, so pointer presses in the zoomed view don't start dragging one. */}
      {zoomed && renderZoom?.(zoomed, () => setZoomedId(null))}
    </DndContext>
  )
}

interface SortableFileProps {
  item: FileItem
  preview?: ReactNode
  disabled?: boolean
  onZoom?: () => void
  onRemove: () => void
}

function SortableFile({ item, preview, disabled, onZoom, onRemove }: SortableFileProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })

  return (
    <li
      ref={setNodeRef}
      className={`file-card${isDragging ? ' file-card-dragging' : ''}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
    >
      <FileCardBody
        file={item.file}
        preview={preview ?? <span className="file-badge">PDF</span>}
        onZoom={disabled ? undefined : onZoom}
        onRemove={disabled ? undefined : onRemove}
      />
    </li>
  )
}
