import type { ReactElement } from 'react'
import CompressPage from './pages/CompressPage'
import ImagesToPdfPage from './pages/ImagesToPdfPage'
import MergePage from './pages/MergePage'

export interface Tool {
  path: string
  title: string
  description: string
  icon: string
  page: ReactElement
}

export const TOOLS: Tool[] = [
  {
    path: '/merge',
    title: 'Merge PDF',
    description: 'Combine multiple PDFs into one file, in the order you choose.',
    icon: '⧉',
    page: <MergePage />,
  },
  {
    path: '/compress',
    title: 'Compress PDF',
    description: 'Reduce file size while keeping the best possible quality.',
    icon: '⇲',
    page: <CompressPage />,
  },
  {
    path: '/images-to-pdf',
    title: 'Image to PDF',
    description: 'Convert JPG and PNG images into a single PDF document.',
    icon: '▣',
    page: <ImagesToPdfPage />,
  },
]
