import type { ReactElement } from 'react'
import compressIcon from './assets/icons/compress.svg'
import imageToPdfIcon from './assets/icons/image-to-pdf.svg'
import mergeIcon from './assets/icons/merge.svg'
import splitIcon from './assets/icons/split.svg'
import CompressPage from './pages/CompressPage'
import ImagesToPdfPage from './pages/ImagesToPdfPage'
import MergePage from './pages/MergePage'
import SplitPage from './pages/SplitPage'

export interface Tool {
  path: string
  title: string
  description: string
  /** URL of the card's icon file. */
  icon: string
  page: ReactElement
  /** Lists the tool's nav link in this column of a header dropdown (see NAV_GROUPS) instead of the top level. */
  navSection?: NavSection
}

/** The header's dropdowns, after the plain links. Each column lists the tools whose `navSection` is its title. */
const NAV_GROUPS = [{ title: 'Convert PDF', sections: ['Convert to PDF', 'Convert from PDF'] }] as const

type NavSection = (typeof NAV_GROUPS)[number]['sections'][number]

export interface NavSectionItems {
  title: string
  tools: Tool[]
}

/** A top-level header nav item: one tool, or a dropdown with columns of tools. */
export type NavItem = { tool: Tool } | { group: string; sections: NavSectionItems[] }

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
    navSection: 'Convert to PDF',
  },
  {
    path: '/split',
    title: 'Split PDF',
    description: 'Split a PDF by page ranges or every few pages, or pull out just the pages you need.',
    icon: splitIcon,
    page: <SplitPage />,
  },
]

/** The header nav: the plain tool links in order, then the dropdowns. */
export const NAV: NavItem[] = [
  ...TOOLS.filter((t) => !t.navSection).map((tool) => ({ tool })),
  ...NAV_GROUPS.map((g) => ({
    group: g.title,
    sections: g.sections.map((title) => ({ title, tools: TOOLS.filter((t) => t.navSection === title) })),
  })),
]
