const MAX_UPLOAD_BYTES = 1024 * 1024 - 1;
const MAX_IMAGE_DIMENSION = 1920;
const JPEG_QUALITIES = [0.82, 0.7, 0.58, 0.46, 0.36];

function loadImage(file: File): Promise<{ image: HTMLImageElement; objectUrl: string }> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => resolve({ image, objectUrl });
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error('无法读取该图片'));
    };
    image.src = objectUrl;
  });
}

function canvasToJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('图片压缩失败'));
    }, 'image/jpeg', quality);
  });
}

/** Keep every uploaded image below 1 MiB. */
export async function compressImageForUpload(file: File): Promise<File> {
  const extension = file.name.split('.').pop()?.toLowerCase();
  if (!['jpg', 'jpeg', 'png', 'gif'].includes(extension || '')) {
    throw new Error('只支持 JPG、PNG 或 GIF 图片');
  }
  if (file.size < MAX_UPLOAD_BYTES) return file;

  const { image, objectUrl } = await loadImage(file);
  try {
    const originalWidth = image.naturalWidth;
    const originalHeight = image.naturalHeight;
    if (!originalWidth || !originalHeight) throw new Error('无法读取该图片尺寸');

    let scale = Math.min(1, MAX_IMAGE_DIMENSION / Math.max(originalWidth, originalHeight));
    for (let resizeAttempt = 0; resizeAttempt < 12; resizeAttempt += 1) {
      const width = Math.max(1, Math.round(originalWidth * scale));
      const height = Math.max(1, Math.round(originalHeight * scale));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('当前浏览器无法压缩图片');

      // JPEG has no alpha channel; flatten transparent PNGs onto white.
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, width, height);
      context.drawImage(image, 0, 0, width, height);

      for (const quality of JPEG_QUALITIES) {
        const blob = await canvasToJpeg(canvas, quality);
        if (blob.size <= MAX_UPLOAD_BYTES) {
          const baseName = file.name.replace(/\.[^.]+$/, '') || 'image';
          return new File([blob], `${baseName}.jpg`, {
            type: 'image/jpeg',
            lastModified: Date.now(),
          });
        }
      }

      scale *= 0.75;
    }
    throw new Error('图片无法压缩到1MB以下，请选择较小的图片');
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
