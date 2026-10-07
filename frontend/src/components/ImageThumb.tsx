import { useCallback } from 'react'

/** Preview of a local image file; the object URL is released when the file changes or the thumb unmounts. */
export default function ImageThumb({ file }: { file: File }) {
  const attach = useCallback(
    (img: HTMLImageElement) => {
      const url = URL.createObjectURL(file)
      img.src = url
      return () => URL.revokeObjectURL(url)
    },
    [file],
  )

  return <img ref={attach} className="file-thumb" alt="" draggable={false} />
}
