"use client";

import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Image as ImageIcon, X } from 'lucide-react';

export interface ImageGalleryProps {
  images: string[];
  alt?: string;
  className?: string;
}

export const ImageGallery: React.FC<ImageGalleryProps> = ({
  images,
  alt = 'Property photo',
  className,
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // No stand-in photo: a listing without images says so rather than showing someone else's flat.
  const displayImages = images;

  const prev = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setCurrentIndex((prev) => (prev === 0 ? displayImages.length - 1 : prev - 1));
  };

  const next = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setCurrentIndex((prev) => (prev === displayImages.length - 1 ? 0 : prev + 1));
  };

  return (
    <div className={`relative overflow-hidden rounded-2xl bg-slate-900 group ${className || ''}`}>
      {/* Main image container */}
      <div
        className={`relative aspect-[16/10] sm:aspect-[2/1] w-full flex items-center justify-center bg-slate-100 ${displayImages.length ? 'cursor-pointer' : ''}`}
        onClick={() => displayImages.length > 0 && setIsFullscreen(true)}
      >
        {displayImages[currentIndex] ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={displayImages[currentIndex]}
            alt={`${alt} - image ${currentIndex + 1}`}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.01]"
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-slate-400">
            <ImageIcon className="w-12 h-12 mb-2" />
            <span className="text-sm font-medium">No photos yet</span>
          </div>
        )}

        {/* Counter badge */}
        {displayImages.length > 1 && (
          <div className="absolute bottom-3 right-3 bg-charcoal/80 text-white text-xs font-semibold px-2.5 py-1 rounded-full backdrop-blur-sm">
            {currentIndex + 1} / {displayImages.length}
          </div>
        )}

        {/* Navigation Arrows */}
        {displayImages.length > 1 && (
          <>
            <button
              onClick={prev}
              aria-label="Previous image"
              className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/80 hover:bg-white text-charcoal shadow-md transition-opacity opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={next}
              aria-label="Next image"
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/80 hover:bg-white text-charcoal shadow-md transition-opacity opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </>
        )}
      </div>

      {/* Thumbnails row */}
      {displayImages.length > 1 && (
        <div className="flex space-x-2 p-2 bg-white border-t border-slate-100 overflow-x-auto no-scrollbar">
          {displayImages.map((img, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentIndex(idx)}
              className={`relative h-14 w-20 shrink-0 rounded-lg overflow-hidden border-2 transition-all ${
                idx === currentIndex ? 'border-forest ring-1 ring-forest' : 'border-transparent opacity-60 hover:opacity-100'
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img} alt={`Thumbnail ${idx + 1}`} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}

      {/* Fullscreen Lightbox Modal */}
      {isFullscreen && (
        <div
          className="fixed inset-0 z-50 bg-black/95 flex flex-col justify-center items-center p-4"
          onClick={() => setIsFullscreen(false)}
        >
          <button
            onClick={() => setIsFullscreen(false)}
            aria-label="Close fullscreen"
            className="absolute top-4 right-4 p-2 text-white/70 hover:text-white rounded-full bg-white/10 hover:bg-white/20 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          <div className="relative max-w-5xl max-h-[85vh] flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={displayImages[currentIndex]}
              alt={`${alt} fullscreen`}
              className="max-h-[85vh] max-w-full object-contain rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          {displayImages.length > 1 && (
            <div className="flex items-center space-x-4 mt-4 text-white text-sm" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={prev}
                aria-label="Previous image"
                className="p-2 rounded-full bg-white/20 hover:bg-white/30"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span>
                {currentIndex + 1} of {displayImages.length}
              </span>
              <button
                onClick={next}
                aria-label="Next image"
                className="p-2 rounded-full bg-white/20 hover:bg-white/30"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
