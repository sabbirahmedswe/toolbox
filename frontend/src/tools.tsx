import type { ReactElement } from 'react'
import MergePage from './pages/MergePage'

export interface Tool {
  path: string
  title: string
  description: string
  icon: string
  /** The tool's page; tools without one show a "Coming soon" placeholder. */
  page?: ReactElement
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
  },
  {
    path: '/images-to-pdf',
    title: 'JPG to PDF',
    description: 'Convert JPG and PNG images into a single PDF document.',
    icon: '▣',
  },
]
