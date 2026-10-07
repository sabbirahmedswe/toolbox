export interface Tool {
  path: string
  title: string
  description: string
  icon: string
}

export const TOOLS: Tool[] = [
  {
    path: '/merge',
    title: 'Merge PDF',
    description: 'Combine multiple PDFs into one file, in the order you choose.',
    icon: '⧉',
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
