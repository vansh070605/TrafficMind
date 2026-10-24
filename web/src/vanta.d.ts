declare module 'vanta/dist/vanta.fog.min' {
  interface VantaOptions {
    el: HTMLElement;
    THREE?: any;
    mouseControls?: boolean;
    touchControls?: boolean;
    gyroControls?: boolean;
    minHeight?: number;
    minWidth?: number;
    highlightColor?: number;
    midtoneColor?: number;
    lowlightColor?: number;
    baseColor?: number;
    blurFactor?: number;
    speed?: number;
    zoom?: number;
  }
  interface VantaEffect {
    destroy: () => void;
  }
  export default function VANTA_FOG(options: VantaOptions): VantaEffect;
}

declare module 'vanta/dist/vanta.waves.min' {
  interface VantaOptions { el: HTMLElement; [key: string]: any; }
  interface VantaEffect { destroy: () => void; }
  export default function VANTA_WAVES(options: VantaOptions): VantaEffect;
}
