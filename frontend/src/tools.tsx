import type { ReactElement } from 'react'
import compressIcon from './assets/icons/compress.svg'
import jpgToPdfIcon from './assets/icons/jpg-to-pdf.svg'
import mergeIcon from './assets/icons/merge.svg'
import pdfToJpgIcon from './assets/icons/pdf-to-jpg.svg'
import splitIcon from './assets/icons/split.svg'
import CompressPage from './pages/CompressPage'
import JpgToPdfPage from './pages/JpgToPdfPage'
import MergePage from './pages/MergePage'
import PdfToJpgPage from './pages/PdfToJpgPage'
import SplitPage from './pages/SplitPage'

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
    path: '/jpg-to-pdf',
    title: 'JPG to PDF',
    description: 'Convert JPG images to PDF in seconds, in any order you like.',
    icon: jpgToPdfIcon,
    page: <JpgToPdfPage />,
  },
  {
    path: '/split',
    title: 'Split PDF',
    description: 'Split a PDF by page ranges or every few pages, or pull out just the pages you need.',
    icon: splitIcon,
    page: <SplitPage />,
  },
  {
    path: '/pdf-to-jpg',
    title: 'PDF to JPG',
    description: 'Turn every page of a PDF into a JPG image, in normal or high quality.',
    icon: pdfToJpgIcon,
    page: <PdfToJpgPage />,
  },
]
