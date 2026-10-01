"use client";

import React from "react";

export interface BorderBeamProps {
  /**
   * The size of the border beam in pixels.
   * @default 200
   */
  size?: number;
  /**
   * The duration of the animation in seconds.
   * @default 6
   */
  duration?: number;
  /**
   * The delay before the animation starts in seconds.
   * @default 0
   */
  delay?: number;
  /**
   * The starting gradient color of the beam.
   * Defaults to Lumen brand primary sky blue (`#38bdf8`).
   * @default "var(--beam-color-from, #38bdf8)"
   */
  colorFrom?: string;
  /**
   * The ending gradient color of the beam.
   * Defaults to Lumen brand deep azure (`#0284c7`).
   * @default "var(--beam-color-to, #0284c7)"
   */
  colorTo?: string;
  /**
   * Whether to reverse the animation direction (counter-clockwise).
   * @default false
   */
  reverse?: boolean;
  /**
   * Initial offset distance percentage along the border path (0-100).
   * @default 0
   */
  initialOffset?: number;
  /**
   * Thickness of the animated border beam line in pixels.
   * @default 1.5
   */
  borderWidth?: number;
  /**
   * Optional additional class name.
   */
  className?: string;
  /**
   * Optional inline style overrides for the outer container.
   */
  style?: React.CSSProperties;
}

/**
 * BorderBeam Component (Magic UI replication)
 *
 * Continuously animates a glowing, perimeter-following light beam around
 * the border of its parent container.
 *
 * Respects parent border-radius, does not alter content dimensions or layout,
 * and maintains `pointer-events: none` to preserve accessibility and click interactions.
 *
 * @example
 * ```tsx
 * <div className="relative rounded-2xl p-6 bg-slate-900 overflow-hidden">
 *   <BorderBeam size={220} duration={6} borderWidth={1.5} colorFrom="#38bdf8" colorTo="#0284c7" />
 *   <p>Card Content</p>
 * </div>
 * ```
 */
export const BorderBeam: React.FC<BorderBeamProps> = ({
  size = 200,
  duration = 6,
  delay = 0,
  colorFrom = "var(--beam-color-from, #38bdf8)",
  colorTo = "var(--beam-color-to, #0284c7)",
  reverse = false,
  initialOffset = 0,
  borderWidth = 1.5,
  className = "",
  style,
}) => {
  return (
    <div
      aria-hidden="true"
      className={`border-beam-container ${className}`.trim()}
      style={{
        pointerEvents: "none",
        position: "absolute",
        inset: 0,
        borderRadius: "inherit",
        padding: `${borderWidth}px`,
        WebkitMask:
          "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
        WebkitMaskComposite: "xor",
        mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
        maskComposite: "exclude",
        overflow: "hidden",
        zIndex: 1,
        ...style,
      }}
    >
      <div
        className={`border-beam-line ${reverse ? "reverse" : ""}`.trim()}
        style={{
          position: "absolute",
          aspectRatio: "1 / 1",
          width: `${size}px`,
          background: `linear-gradient(to left, ${colorFrom}, ${colorTo}, transparent)`,
          offsetPath: `rect(0 auto auto 0 round ${size}px)`,
          animation: `border-beam-travel ${duration}s linear infinite`,
          animationDelay: `${-delay}s`,
          animationDirection: reverse ? "reverse" : "normal",
          filter: "drop-shadow(0 0 8px var(--beam-glow, rgba(56, 189, 248, 0.35)))",
          offsetDistance: initialOffset ? `${initialOffset}%` : undefined,
        }}
      />
    </div>
  );
};

export default BorderBeam;
