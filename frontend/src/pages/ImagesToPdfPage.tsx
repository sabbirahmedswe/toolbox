import ImageThumb from '../components/ImageThumb'
import MultiFileTool from '../components/MultiFileTool'

export default function ImagesToPdfPage() {
  return (
    <MultiFileTool
      endpoint="/api/images-to-pdf"
      fallbackName="images.pdf"
      accept={{ 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'] }}
      minFiles={1}
      title="Convert images to PDF"
      subtitle="Turn JPG and PNG images into a single PDF, one image per page."
      sidebarTitle="Image to PDF"
      selectLabel="Select images"
      hint="or drop JPG or PNG images here"
      addMoreLabel="Add more images"
      reorderHint="Drag and drop the images to set the page order"
      actionLabel="Convert to PDF"
      busyLabel="Converting…"
      doneTitle="Your images have been converted to PDF!"
      downloadLabel="Download PDF"
      againLabel="Convert more images"
      renderPreview={(item) => <ImageThumb file={item.file} />}
    />
  )
}
