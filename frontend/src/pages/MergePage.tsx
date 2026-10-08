import MultiFileTool from '../components/MultiFileTool'
import PdfThumb from '../components/PdfThumb'

export default function MergePage() {
  return (
    <MultiFileTool
      endpoint="/api/merge"
      fallbackName="merged.pdf"
      accept={{ 'application/pdf': ['.pdf'] }}
      minFiles={2}
      title="Merge PDF files"
      subtitle="Combine several PDFs into one document, in exactly the order you choose."
      sidebarTitle="Merge"
      selectLabel="Select PDF files"
      hint="or drop PDFs here"
      addMoreLabel="Add more files"
      minFilesHint="Add at least 2 PDFs to merge."
      reorderHint="To change the order of your PDFs, drag and drop the files as you want."
      actionLabel="Merge PDF"
      busyLabel="Merging…"
      doneTitle="Your PDFs have been merged!"
      downloadLabel="Download merged PDF"
      againLabel="Merge more files"
      sortByName
      renderPreview={(item) => <PdfThumb file={item.file} />}
    />
  )
}
