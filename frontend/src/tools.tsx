import type { ReactElement } from 'react'
import compressIcon from './assets/icons/compress.svg'
import imageToPdfIcon from './assets/icons/image-to-pdf.svg'
import mergeIcon from './assets/icons/merge.svg'
import CompressPage from './pages/CompressPage'
import ImagesToPdfPage from './pages/ImagesToPdfPage'
import MergePage from './pages/MergePage'

export interface Tool {
  path: string
  title: string
  description: string
  /** URL of the card's icon file. */
  icon: string
  page: ReactElement
}

export const TOOLS: Tool[] = [
  {
    path: '/merge',
    title: 'Merge PDF',
    description: 'Combine PDFs in the order you want with the easiest PDF merger available.',
    icon: mergeIcon,
    page: <MergePage />,
  },
  {
    path: '/compress',
    title: 'Compress PDF',
    description: 'Reduce the file size of your PDF while keeping the best possible quality.',
    icon: compressIcon,
    page: <CompressPage />,
  },
  {
    path: '/images-to-pdf',
    title: 'Image to PDF',
    description: 'Convert JPG and PNG images to PDF in seconds, in any order you like.',
    icon: imageToPdfIcon,
    page: <ImagesToPdfPage />,
  },
]
