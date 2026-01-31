import * as React from 'react';
import {
  Modal,
  ModalVariant,
  Button,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Gallery,
  GalleryItem,
  Alert,
  AlertVariant,
} from '@patternfly/react-core';
import { DownloadIcon, CopyIcon, ExclamationTriangleIcon } from '@patternfly/react-icons';

import './ImagePreview.css';

interface ImagePreviewProps {
  content: string;
}

interface ImageModalState {
  isOpen: boolean;
  imageUrl: string;
  altText: string;
}

interface ImageError {
  url: string;
  message: string;
}

interface SecurityValidationResult {
  isValid: boolean;
  reason?: string;
}

interface ImageLoadState {
  loading: boolean;
  error: string | null;
  hasLoadError: boolean;
}

interface DetectedImage {
  url: string;
  alt: string;
  isValid: boolean;
  validationError?: string;
}

// =============================================================================
// Constants
// =============================================================================

const ALLOWED_PROTOCOLS = ['https:', 'http:'];
const ALLOWED_IMAGE_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/gif',
  'image/webp',
  'image/svg+xml',
];
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB
const MAX_FILE_SIZE_ERROR = 'File size exceeds limit (50MB max)';

const MARKDOWN_IMAGE_REGEX = /!\[([^\]]*)\]\(([^)]+)\)/g;
const STANDALONE_IMAGE_URL_REGEX = /https?:\/\/[^\s]+\.(jpg|jpeg|png|gif|webp|svg)(\?[^\s]*)?/gi;

const PRIVATE_NETWORK_PREFIXES = ['192.168.', '10.', '172.'];
const LOCAL_HOSTNAMES = ['localhost', '127.0.0.1', '0.0.0.0'];

// =============================================================================
// Validation Functions
// =============================================================================

function isLocalDevelopment(): boolean {
  const hostname = window.location.hostname;
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

function isPrivateNetworkHost(hostname: string): boolean {
  if (LOCAL_HOSTNAMES.includes(hostname)) return true;
  if (hostname.includes('..')) return true;
  return PRIVATE_NETWORK_PREFIXES.some((prefix) => hostname.startsWith(prefix));
}

function validateImageUrl(url: string): SecurityValidationResult {
  try {
    const urlObj = new URL(url);

    if (!ALLOWED_PROTOCOLS.includes(urlObj.protocol)) {
      return { isValid: false, reason: 'Invalid protocol. Only HTTP and HTTPS are allowed.' };
    }

    const hostname = urlObj.hostname.toLowerCase();
    if (!isLocalDevelopment() && isPrivateNetworkHost(hostname)) {
      return { isValid: false, reason: 'Access to local/private networks is not allowed.' };
    }

    return { isValid: true };
  } catch {
    return { isValid: false, reason: 'Invalid URL format.' };
  }
}

async function validateImageType(url: string): Promise<SecurityValidationResult> {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    const contentType = response.headers.get('content-type');

    if (!contentType || !ALLOWED_IMAGE_TYPES.some((type) => contentType.startsWith(type))) {
      return { isValid: false, reason: 'Invalid content type. Only image files are allowed.' };
    }

    const contentLength = response.headers.get('content-length');
    if (contentLength && parseInt(contentLength) > MAX_FILE_SIZE_BYTES) {
      return { isValid: false, reason: MAX_FILE_SIZE_ERROR };
    }

    return { isValid: true };
  } catch {
    return { isValid: false, reason: 'Unable to validate image.' };
  }
}

// =============================================================================
// Clipboard Utilities
// =============================================================================

function copyToClipboardFallback(text: string): void {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand('copy');
  document.body.removeChild(textArea);
}

async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
  } else {
    copyToClipboardFallback(text);
  }
}

// =============================================================================
// Component
// =============================================================================

export function ImagePreview({ content }: ImagePreviewProps): React.ReactElement | null {
  const [imageModal, setImageModal] = React.useState<ImageModalState>({
    isOpen: false,
    imageUrl: '',
    altText: '',
  });

  const [imageErrors, setImageErrors] = React.useState<Record<string, ImageError>>({});
  const [imageLoadStates, setImageLoadStates] = React.useState<Record<string, ImageLoadState>>({});
  const [clipboardError, setClipboardError] = React.useState<string | null>(null);

  const detectedImages = React.useMemo(() => {
    const images: DetectedImage[] = [];
    const existingUrls = new Set<string>();

    // Extract markdown images: ![alt](url)
    const markdownRegex = new RegExp(MARKDOWN_IMAGE_REGEX.source, 'g');
    let match;
    while ((match = markdownRegex.exec(content)) !== null) {
      const url = match[2];
      const validation = validateImageUrl(url);
      images.push({
        url,
        alt: match[1] || 'Image',
        isValid: validation.isValid,
        validationError: validation.reason,
      });
      existingUrls.add(url);
    }

    // Extract standalone image URLs (not already in markdown)
    const standaloneRegex = new RegExp(STANDALONE_IMAGE_URL_REGEX.source, 'gi');
    while ((match = standaloneRegex.exec(content)) !== null) {
      const url = match[0];
      if (!existingUrls.has(url)) {
        const validation = validateImageUrl(url);
        images.push({
          url,
          alt: 'Image',
          isValid: validation.isValid,
          validationError: validation.reason,
        });
        existingUrls.add(url);
      }
    }

    return images;
  }, [content]);

  const handleImageClick = (url: string, alt: string) => {
    const validation = validateImageUrl(url);
    if (!validation.isValid) {
      setImageErrors((prev) => ({
        ...prev,
        [url]: { url, message: validation.reason || 'Invalid image URL' },
      }));
      return;
    }

    setImageModal({ isOpen: true, imageUrl: url, altText: alt });
  };

  const handleKeyDown = (event: React.KeyboardEvent, url: string, alt: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleImageClick(url, alt);
    }
  };

  const setImageLoadState = (url: string, state: Partial<ImageLoadState>) => {
    setImageLoadStates((prev) => ({
      ...prev,
      [url]: { ...prev[url], ...state },
    }));
  };

  const handleImageError = (url: string, errorMessage: string) => {
    setImageErrors((prev) => ({
      ...prev,
      [url]: { url, message: errorMessage },
    }));
    setImageLoadState(url, { hasLoadError: true, loading: false, error: errorMessage });
  };

  const handleCloseModal = () => {
    setImageModal({ isOpen: false, imageUrl: '', altText: '' });
    setClipboardError(null);
  };

  const handleDownload = async () => {
    try {
      const urlValidation = validateImageUrl(imageModal.imageUrl);
      if (!urlValidation.isValid) {
        setImageErrors((prev) => ({
          ...prev,
          [imageModal.imageUrl]: {
            url: imageModal.imageUrl,
            message: urlValidation.reason || 'Invalid URL',
          },
        }));
        return;
      }

      const typeValidation = await validateImageType(imageModal.imageUrl);
      if (!typeValidation.isValid) {
        setImageErrors((prev) => ({
          ...prev,
          [imageModal.imageUrl]: {
            url: imageModal.imageUrl,
            message: typeValidation.reason || 'Invalid image type',
          },
        }));
        return;
      }

      const response = await fetch(imageModal.imageUrl);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentLength = response.headers.get('content-length');
      if (contentLength && parseInt(contentLength) > MAX_FILE_SIZE_BYTES) {
        throw new Error(MAX_FILE_SIZE_ERROR);
      }

      const blob = await response.blob();

      if (blob.size > MAX_FILE_SIZE_BYTES) {
        throw new Error(MAX_FILE_SIZE_ERROR);
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const filename = imageModal.imageUrl.split('/').pop()?.split('?')[0] || 'image';
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Error downloading image';
      console.error('Error downloading image:', error);
      setImageErrors((prev) => ({
        ...prev,
        [imageModal.imageUrl]: { url: imageModal.imageUrl, message: errorMessage },
      }));
    }
  };

  const handleCopyUrl = async () => {
    setClipboardError(null);
    try {
      await copyToClipboard(imageModal.imageUrl);
    } catch (error) {
      console.error('Error copying to clipboard:', error);
      // Try fallback method
      try {
        copyToClipboardFallback(imageModal.imageUrl);
      } catch (fallbackError) {
        console.error('Fallback copy method also failed:', fallbackError);
        setClipboardError('Failed to copy URL to clipboard');
      }
    }
  };

  const validImages = detectedImages.filter((img) => img.isValid);
  const invalidImages = detectedImages.filter((img) => !img.isValid);

  if (validImages.length === 0 && invalidImages.length === 0) {
    return null;
  }

  return (
    <>
      <div className="image-preview-container">
        {invalidImages.length > 0 && (
          <div className="image-preview-invalid-section">
            {invalidImages.map((image, index) => (
              <Alert
                key={`invalid-${image.url}-${index}`}
                variant={AlertVariant.warning}
                title="Invalid Image URL"
                className="image-preview-alert"
              >
                {image.validationError}: {image.url}
              </Alert>
            ))}
          </div>
        )}

        {Object.values(imageErrors).map((error, index) => (
          <Alert
            key={`error-${error.url}-${index}`}
            variant={AlertVariant.danger}
            title="Image Load Error"
            className="image-preview-alert"
          >
            {error.message}: {error.url}
          </Alert>
        ))}

        {validImages.length > 0 && (
          <Gallery hasGutter minWidths={{ default: '300px', md: '400px' }}>
            {validImages.map((image, index) => {
              const loadState = imageLoadStates[image.url] || {
                loading: false,
                error: null,
                hasLoadError: false,
              };
              const hasError = imageErrors[image.url] || loadState.hasLoadError;

              return (
                <GalleryItem key={`${image.url}-${index}`}>
                  <div
                    role="button"
                    tabIndex={0}
                    aria-label={`View image: ${image.alt}`}
                    className="image-preview-button"
                    onClick={() => handleImageClick(image.url, image.alt)}
                    onKeyDown={(e) => handleKeyDown(e, image.url, image.alt)}
                  >
                    {hasError ? (
                      <div className="image-preview-error-placeholder">
                        <ExclamationTriangleIcon className="image-preview-error-icon" />
                        <div>Failed to load image</div>
                        <div className="image-preview-error-detail">
                          {loadState.error || 'Unknown error'}
                        </div>
                      </div>
                    ) : (
                      <img
                        src={image.url}
                        alt={image.alt}
                        className="image-preview-thumbnail"
                        onError={() => {
                          handleImageError(image.url, 'Failed to load image');
                        }}
                        onLoad={() => {
                          setImageLoadState(image.url, {
                            loading: false,
                            error: null,
                            hasLoadError: false,
                          });
                        }}
                        onLoadStart={() => {
                          setImageLoadState(image.url, {
                            loading: true,
                            error: null,
                            hasLoadError: false,
                          });
                        }}
                      />
                    )}
                  </div>
                </GalleryItem>
              );
            })}
          </Gallery>
        )}
      </div>

      <Modal
        variant={ModalVariant.large}
        isOpen={imageModal.isOpen}
        onClose={handleCloseModal}
        aria-labelledby="image-preview-modal"
        aria-describedby="image-preview-modal-description"
      >
        <ModalHeader
          title="Image Preview"
          labelId="image-preview-modal"
          descriptorId="image-preview-modal-description"
        />
        <ModalBody>
          {clipboardError && (
            <Alert variant={AlertVariant.danger} title="Clipboard Error" className="image-preview-alert">
              {clipboardError}
            </Alert>
          )}

          {imageErrors[imageModal.imageUrl] && (
            <Alert variant={AlertVariant.danger} title="Image Error" className="image-preview-alert">
              {imageErrors[imageModal.imageUrl].message}
            </Alert>
          )}

          <div className="image-preview-modal-center">
            <img
              src={imageModal.imageUrl}
              alt={imageModal.altText}
              className="image-preview-modal-image"
              onError={() => {
                handleImageError(imageModal.imageUrl, 'Failed to load image in preview');
              }}
            />
          </div>
        </ModalBody>
        <ModalFooter>
          <Button
            key="download"
            variant="secondary"
            onClick={handleDownload}
            icon={<DownloadIcon />}
            isDisabled={!!imageErrors[imageModal.imageUrl]}
          >
            Download
          </Button>
          <Button key="copy" variant="secondary" onClick={handleCopyUrl} icon={<CopyIcon />}>
            Copy URL
          </Button>
          <Button key="close" variant="primary" onClick={handleCloseModal}>
            Close
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
};
