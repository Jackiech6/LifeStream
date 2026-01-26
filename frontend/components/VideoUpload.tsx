'use client';

import { useState, useCallback, useRef } from 'react';
import { apiClient } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { useRouter } from 'next/navigation';

const ALLOWED_TYPES = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/webm'];
const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024; // 2GB

export default function VideoUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { setActiveJob, updateJobStatus } = useAppStore();

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return 'Invalid file type. Please upload MP4, MOV, AVI, MKV, or WebM files.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds 2GB limit. Current size: ${(file.size / 1024 / 1024).toFixed(2)}MB`;
    }
    return null;
  };

  const handleFileSelect = useCallback((selectedFile: File) => {
    const validationError = validateFile(selectedFile);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setFile(selectedFile);
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }, [handleFileSelect]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  }, [handleFileSelect]);

  const getVideoDurationSeconds = (f: File): Promise<number | null> => {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(f);
      const video = document.createElement('video');
      video.preload = 'metadata';
      video.onloadedmetadata = () => {
        URL.revokeObjectURL(url);
        resolve(Number.isFinite(video.duration) ? video.duration : null);
      };
      video.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(null);
      };
      video.src = url;
    });
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setProgress(0);

    try {
      // Step 1: Get presigned URL
      const presignedResponse = await apiClient.generatePresignedUrl({
        filename: file.name,
        file_size: file.size,
      });

      // Step 2: Upload to S3
      await apiClient.uploadToS3(
        presignedResponse.upload_url,
        file,
        (uploadProgress) => {
          setProgress(uploadProgress * 0.9); // 90% for upload
        }
      );

      // Step 3: Client-side duration (for backend diagnostics; user-reported 1.5 min vs 5.5 min)
      const clientDuration = await getVideoDurationSeconds(file);
      const metadata: Record<string, unknown> = {};
      if (clientDuration != null) metadata.client_duration_seconds = clientDuration;

      // Step 4: Confirm upload
      setProgress(95);
      const confirmResponse = await apiClient.confirmUpload({
        job_id: presignedResponse.job_id,
        s3_key: presignedResponse.s3_key,
        metadata: Object.keys(metadata).length ? metadata : undefined,
      });

      setProgress(100);

      // Update store and navigate
      setActiveJob(confirmResponse.job_id);
      updateJobStatus(confirmResponse.job_id, {
        job_id: confirmResponse.job_id,
        status: 'queued',
      });

      // Navigate to job status page
      router.push(`/jobs/${confirmResponse.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-6">
      <h2 className="text-2xl font-bold bg-gradient-to-r from-primary-700 to-primary-500 bg-clip-text text-transparent mb-6">Upload Video</h2>

      {/* Drag and Drop Area */}
      <div
        className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 ${
          dragActive
            ? 'border-primary-500 bg-primary-50/80'
            : 'border-gray-300 hover:border-primary-400 hover:bg-white/60'
        } ${uploading ? 'opacity-50 pointer-events-none' : 'cursor-pointer'} bg-white/50 backdrop-blur-sm`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleFileInputChange}
          className="hidden"
          disabled={uploading}
        />

        {file ? (
          <div className="space-y-4">
            <div className="text-4xl">📹</div>
            <div>
              <p className="font-semibold text-lg">{file.name}</p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            {!uploading && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="text-sm text-red-600 hover:text-red-700"
              >
                Remove file
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-6xl">📤</div>
            <div>
              <p className="text-lg font-semibold">Drag and drop your video here</p>
              <p className="text-sm text-gray-500 mt-2">or click to browse</p>
            </div>
            <p className="text-xs text-gray-400">
              Supported formats: MP4, MOV, AVI, MKV, WebM (max 2GB)
            </p>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      {uploading && (
        <div className="mt-6">
          <div className="flex justify-between text-sm mb-2">
            <span>Uploading...</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-primary-600 to-primary-500 h-2.5 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50/90 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Upload Button */}
      {file && !uploading && (
        <button
          onClick={handleUpload}
          className="mt-6 w-full bg-gradient-to-r from-primary-600 to-primary-500 text-white py-3 px-6 rounded-xl font-semibold hover:from-primary-700 hover:to-primary-600 shadow-md hover:shadow-lg transition-all duration-300"
        >
          Upload Video
        </button>
      )}
    </div>
  );
}
