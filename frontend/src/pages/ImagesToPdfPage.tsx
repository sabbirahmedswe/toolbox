import ImageThumb from '../components/ImageThumb'
import MultiFileTool from '../components/MultiFileTool'

export default function ImagesToPdfPage() {
  return (
    <MultiFileTool
      endpoint="/api/images-to-pdf"
      fallbackName="images.pdf"
      accept={{ 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'] }}
      minFiles={1}
      title="Image to PDF"
      subtitle="Convert JPG and PNG images to PDF, one image per page. Drag images to reorder them."
      selectLabel="Select images"
      hint="or drop JPG or PNG images here"
      addMoreLabel="Add more images"
      actionLabel="Convert to PDF"
      busyLabel="Converting…"
      doneTitle="Your images have been converted to PDF!"
      downloadLabel="Download PDF"
      againLabel="Convert more images"
      renderPreview={(item) => <ImageThumb file={item.file} />}
    />
  )
}
