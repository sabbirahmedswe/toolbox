import MultiFileTool from '../components/MultiFileTool'

export default function MergePage() {
  return (
    <MultiFileTool
      endpoint="/api/merge"
      fallbackName="merged.pdf"
      accept={{ 'application/pdf': ['.pdf'] }}
      minFiles={2}
      title="Merge PDF files"
      subtitle="Combine PDFs in the order you want. Drag files to reorder them."
      selectLabel="Select PDF files"
      hint="or drop PDFs here"
      addMoreLabel="Add more files"
      minFilesHint="Add at least 2 PDFs to merge."
      reorderHint="Drag and drop the files to set the merge order"
      actionLabel="Merge PDF"
      busyLabel="Merging…"
      doneTitle="Your PDFs have been merged!"
      downloadLabel="Download merged PDF"
      againLabel="Merge more files"
    />
  )
}
