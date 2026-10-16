import ImageThumb from '../components/ImageThumb'
import MultiFileTool from '../components/MultiFileTool'

export default function JpgToPdfPage() {
  return (
    <MultiFileTool
      endpoint="/api/jpg-to-pdf"
      fallbackName="images.pdf"
      accept={{ 'image/jpeg': ['.jpg', '.jpeg', '.jpe', '.jfif', '.pjpeg', '.pjp'] }}
      minFiles={1}
      title="Convert JPG to PDF"
      subtitle="Turn JPG images into a single PDF, one image per page."
      sidebarTitle="JPG to PDF"
      selectLabel="Select JPG images"
      hint="or drop JPG images here"
      addMoreLabel="Add more JPG images"
      reorderHint="Drag and drop the JPG images to set the page order"
      actionLabel="Convert to PDF"
      busyLabel="Converting…"
      doneTitle="Your JPG images have been converted to PDF!"
      downloadLabel="Download PDF"
      againLabel="Convert more JPG images"
      renderPreview={(item) => <ImageThumb file={item.file} />}
    />
  )
}
