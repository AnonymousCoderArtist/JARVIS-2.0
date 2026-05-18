import { useEffect, useRef } from "react";

const SPHERE_STROKE_BASE = { r: 26, g: 90, b: 255 };
const SPHERE_STROKE_SEC_BASE = { r: 0, g: 68, b: 204 };

interface TechSphereProps {
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function TechSphere({ onClick, className, style }: TechSphereProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const mainPaths = svgEl.querySelectorAll<SVGPathElement>(
      ".sphere-main path"
    );
    const secondaryPaths = svgEl.querySelectorAll<SVGPathElement>(
      ".sphere-secondary path"
    );
    const totalMain = mainPaths.length;
    const totalSec = secondaryPaths.length;

    const mainAnimData: {
      el: SVGPathElement;
      baseStroke: number;
      offset: number;
      speed: number;
    }[] = [];
    const secAnimData: {
      el: SVGPathElement;
      baseStroke: number;
      offset: number;
      speed: number;
    }[] = [];
    let startTime = performance.now();

    for (let i = 0; i < totalMain; i++) {
      mainAnimData.push({
        el: mainPaths[i],
        baseStroke: 2.5,
        offset: i * 0.4,
        speed: 0.0025,
      });
    }

    for (let i = 0; i < totalSec; i++) {
      secAnimData.push({
        el: secondaryPaths[i],
        baseStroke: 2,
        offset: i * 0.45,
        speed: 0.003,
      });
    }

    let animRaf = 0;

    function animate(timestamp: number) {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;

      for (let i = 0; i < totalMain; i++) {
        const data = mainAnimData[i];
        const percent = (1 - Math.sin(data.offset + data.speed * elapsed)) / 2;
        const strokeVal = 2.5 + percent * 1.0;
        const alpha = 0.7 + percent * 0.3;
        data.el.style.strokeWidth = String(strokeVal);
        data.el.style.stroke = `rgba(${Math.round(SPHERE_STROKE_BASE.r + percent * 54)}, ${Math.round(SPHERE_STROKE_BASE.g + percent * 70)}, 255, ${alpha})`;
        data.el.style.transform = `translate(${(percent - 0.5) * 5}px, ${(percent - 0.5) * 5}px)`;
      }

      for (let i = 0; i < totalSec; i++) {
        const data = secAnimData[i];
        const percent = (1 - Math.cos(data.offset + data.speed * elapsed)) / 2;
        const alpha = 0.4 + percent * 0.5;
        data.el.style.stroke = `rgba(${Math.round(SPHERE_STROKE_SEC_BASE.r + percent * 34)}, ${Math.round(SPHERE_STROKE_SEC_BASE.g + percent * 112)}, ${Math.round(SPHERE_STROKE_SEC_BASE.b + percent * 51)}, ${alpha})`;
        data.el.style.strokeWidth = String(2 + percent * 0.8);
        data.el.style.transform = `translate(${(percent - 0.5) * 5}px, ${(percent - 0.5) * 5}px)`;
      }

      animRaf = requestAnimationFrame(animate);
    }

    function introAnimation() {
      if (typeof (window as any).anime === "undefined") {
        startTime = performance.now();
        animRaf = requestAnimationFrame(animate);
        return;
      }

      const anime = (window as any).anime;

      anime({
        targets: mainPaths,
        strokeDashoffset: [anime.setDashoffset, 0],
        duration: 2500,
        easing: "easeInOutCirc",
        delay: anime.stagger(120, { direction: "reverse" }),
        complete: function () {
          startTime = performance.now();
          animRaf = requestAnimationFrame(animate);
        },
      });

      anime({
        targets: secondaryPaths,
        opacity: [0, 0.5],
        duration: 1500,
        easing: "easeInOutQuad",
        delay: anime.stagger(60),
      });
    }

    introAnimation();

    let mouseX = 0,
      mouseY = 0;
    let targetRX = 0,
      targetRY = 0;

    const onMouseMove = (e: MouseEvent) => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 2;
      mouseX = (e.clientX - cx) / cx;
      mouseY = (e.clientY - cy) / cy;
    };

    let tiltRaf = 0;
    function updateTilt() {
      targetRX += (mouseY * 15 - targetRX) * 0.05;
      targetRY += (mouseX * 15 - targetRY) * 0.05;
      if (containerRef.current) {
        containerRef.current.style.transform = `rotateX(${targetRX}deg) rotateY(${targetRY}deg)`;
      }
      tiltRaf = requestAnimationFrame(updateTilt);
    }

    document.addEventListener("mousemove", onMouseMove);
    tiltRaf = requestAnimationFrame(updateTilt);

    return () => {
      cancelAnimationFrame(animRaf);
      cancelAnimationFrame(tiltRaf);
      document.removeEventListener("mousemove", onMouseMove);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        perspective: "800px",
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
      onClick={onClick}
    >
      <svg
        ref={svgRef}
        className="sphere-svg"
        viewBox="0 0 440 440"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          width: 200,
          height: 200,
          filter: `drop-shadow(0 0 20px rgba(${SPHERE_STROKE_BASE.r}, ${SPHERE_STROKE_BASE.g}, ${SPHERE_STROKE_BASE.b}, 0.3))`,
          willChange: "transform",
        }}
      >
        <defs>
          <linearGradient
            id="strokeGradient"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#1a5aff" />
            <stop offset="25%" stopColor="#0066ff" />
            <stop offset="50%" stopColor="#4a8aff" />
            <stop offset="75%" stopColor="#0055dd" />
            <stop offset="100%" stopColor="#1a5aff" />
          </linearGradient>

          <linearGradient
            id="strokeGradient2"
            x1="100%"
            y1="100%"
            x2="0%"
            y2="0%"
          >
            <stop offset="0%" stopColor="#0044cc" />
            <stop offset="50%" stopColor="#2277ff" />
            <stop offset="100%" stopColor="#0044cc" />
          </linearGradient>

          <radialGradient
            id="coreGradient"
            cx="50%"
            cy="50%"
            r="50%"
          >
            <stop offset="0%" stopColor="#0a0a18" />
            <stop offset="70%" stopColor="#03030a" />
            <stop offset="100%" stopColor="#000" />
          </radialGradient>

          <linearGradient
            id="pathFillGradient"
            x1="5%"
            y1="0%"
            x2="95%"
            y2="100%"
          >
            <stop offset="0%" stopColor="#0a1530" />
            <stop offset="50%" stopColor="#081028" />
            <stop offset="100%" stopColor="#050a18" />
          </linearGradient>

          <filter id="lineGlow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="1.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle cx="220" cy="220" r="210" fill="url(#coreGradient)" />

        <g
          className="sphere-main"
          stroke="url(#strokeGradient)"
          strokeWidth="2.5"
          fill="url(#pathFillGradient)"
          filter="url(#lineGlow)"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M361.604 361.238c-24.407 24.408-51.119 37.27-59.662 28.727-8.542-8.543 4.319-35.255 28.726-59.663 24.408-24.407 51.12-37.269 59.663-28.726 8.542 8.543-4.319 35.255-28.727 59.662z" />
          <path d="M360.72 360.354c-35.879 35.88-75.254 54.677-87.946 41.985-12.692-12.692 6.105-52.067 41.985-87.947 35.879-35.879 75.254-54.676 87.946-41.984 12.692 12.692-6.105 52.067-41.984 87.946z" />
          <path d="M357.185 356.819c-44.91 44.91-94.376 68.258-110.485 52.149-16.11-16.11 7.238-65.575 52.149-110.485 44.91-44.91 94.376-68.259 110.485-52.15 16.11 16.11-7.239 65.576-52.149 110.486z" />
          <path d="M350.998 350.632c-53.21 53.209-111.579 81.107-130.373 62.313-18.794-18.793 9.105-77.163 62.314-130.372 53.209-53.21 111.579-81.108 130.373-62.314 18.794 18.794-9.105 77.164-62.314 130.373z" />
          <path d="M343.043 342.677c-59.8 59.799-125.292 91.26-146.283 70.268-20.99-20.99 10.47-86.483 70.269-146.282 59.799-59.8 125.292-91.26 146.283-70.269 20.99 20.99-10.47 86.484-70.27 146.283z" />
          <path d="M334.646 334.28c-65.169 65.169-136.697 99.3-159.762 76.235-23.065-23.066 11.066-94.593 76.235-159.762s136.697-99.3 159.762-76.235c23.065 23.065-11.066 94.593-76.235 159.762z" />
          <path d="M324.923 324.557c-69.806 69.806-146.38 106.411-171.031 81.76-24.652-24.652 11.953-101.226 81.759-171.032 69.806-69.806 146.38-106.411 171.031-81.76 24.652 24.653-11.953 101.226-81.759 171.032z" />
          <path d="M312.99 312.625c-73.222 73.223-153.555 111.609-179.428 85.736-25.872-25.872 12.514-106.205 85.737-179.428s153.556-111.609 179.429-85.737c25.872 25.873-12.514 106.205-85.737 179.429z" />
          <path d="M300.175 299.808c-75.909 75.909-159.11 115.778-185.837 89.052-26.726-26.727 13.143-109.929 89.051-185.837 75.908-75.908 159.11-115.778 185.837-89.051 26.726 26.726-13.143 109.928-89.051 185.836z" />
          <path d="M284.707 284.34c-77.617 77.617-162.303 118.773-189.152 91.924-26.848-26.848 14.308-111.534 91.924-189.15C265.096 109.496 349.782 68.34 376.63 95.188c26.849 26.849-14.307 111.535-91.923 189.151z" />
          <path d="M269.239 267.989c-78.105 78.104-163.187 119.656-190.035 92.807-26.849-26.848 14.703-111.93 92.807-190.035 78.105-78.104 163.187-119.656 190.035-92.807 26.849 26.848-14.703 111.93-92.807 190.035z" />
          <path d="M252.887 252.52C175.27 330.138 90.584 371.294 63.736 344.446 36.887 317.596 78.043 232.91 155.66 155.293 233.276 77.677 317.962 36.521 344.81 63.37c26.85 26.848-14.307 111.534-91.923 189.15z" />
          <path d="M236.977 236.61C161.069 312.52 77.867 352.389 51.14 325.663c-26.726-26.727 13.143-109.928 89.052-185.837 75.908-75.908 159.11-115.777 185.836-89.05 26.727 26.726-13.143 109.928-89.051 185.836z" />
          <path d="M221.067 220.7C147.844 293.925 67.51 332.31 41.639 306.439c-25.873-25.873 12.513-106.206 85.736-179.429C200.6 53.786 280.931 15.4 306.804 41.272c25.872 25.873-12.514 106.206-85.737 179.429z" />
          <path d="M205.157 204.79c-69.806 69.807-146.38 106.412-171.031 81.76-24.652-24.652 11.953-101.225 81.759-171.031 69.806-69.807 146.38-106.411 171.031-81.76 24.652 24.652-11.953 101.226-81.759 171.032z" />
          <path d="M189.247 188.881c-65.169 65.169-136.696 99.3-159.762 76.235-23.065-23.065 11.066-94.593 76.235-159.762s136.697-99.3 159.762-76.235c23.065 23.065-11.066 94.593-76.235 159.762z" />
          <path d="M173.337 172.971c-59.799 59.8-125.292 91.26-146.282 70.269-20.991-20.99 10.47-86.484 70.268-146.283 59.8-59.799 125.292-91.26 146.283-70.269 20.99 20.991-10.47 86.484-70.269 146.283z" />
          <path d="M157.427 157.061c-53.209 53.21-111.578 81.108-130.372 62.314-18.794-18.794 9.104-77.164 62.313-130.373 53.21-53.209 111.58-81.108 130.373-62.314 18.794 18.794-9.105 77.164-62.314 130.373z" />
          <path d="M141.517 141.151c-44.91 44.91-94.376 68.259-110.485 52.15-16.11-16.11 7.239-65.576 52.15-110.486 44.91-44.91 94.375-68.258 110.485-52.15 16.109 16.11-7.24 65.576-52.15 110.486z" />
          <path d="M125.608 125.241c-35.88 35.88-75.255 54.677-87.947 41.985-12.692-12.692 6.105-52.067 41.985-87.947C115.525 43.4 154.9 24.603 167.592 37.295c12.692 12.692-6.105 52.067-41.984 87.946z" />
          <path d="M109.698 109.332c-24.408 24.407-51.12 37.268-59.663 28.726-8.542-8.543 4.319-35.255 28.727-59.662 24.407-24.408 51.12-37.27 59.662-28.727 8.543 8.543-4.319 35.255-28.726 59.663z" />
        </g>

        <g
          className="sphere-secondary"
          stroke="url(#strokeGradient2)"
          strokeWidth="2"
          fill="none"
          filter="url(#lineGlow)"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.5"
        >
          <path d="M361.604 361.238c-24.407 24.408-51.119 37.27-59.662 28.727" />
          <path d="M357.185 356.819c-44.91 44.91-94.376 68.258-110.485 52.149" />
          <path d="M350.998 350.632c-53.21 53.209-111.579 81.107-130.373 62.313" />
          <path d="M343.043 342.677c-59.8 59.799-125.292 91.26-146.283 70.268" />
          <path d="M300.175 299.808c-75.909 75.909-159.11 115.778-185.837 89.052" />
          <path d="M252.887 252.52C175.27 330.138 90.584 371.294 63.736 344.446" />
          <path d="M236.977 236.61C161.069 312.52 77.867 352.389 51.14 325.663" />
          <path d="M221.067 220.7C147.844 293.925 67.51 332.31 41.639 306.439" />
          <path d="M125.608 125.241c-35.88 35.88-75.255 54.677-87.947 41.985" />
          <path d="M109.698 109.332c-24.408 24.407-51.12 37.268-59.663 28.726" />
        </g>
      </svg>
    </div>
  );
}
