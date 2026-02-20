import logo from '@/assets/logo.svg'

interface TitleBarProps {
}

export function TitleBar({ }: TitleBarProps) {
  return (
    <header
      className="fixed top-0 left-0 right-0 h-[48px] z-50 flex items-center justify-between px-2 select-none border-b border-border/40 bg-background/80 backdrop-blur-sm"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* 左側：macOSの信号機ボタン用のスペース */}
      <div className="w-20 h-full flex items-center" />

      {/* 中央：ロゴ */}
      <div
        className="flex-1 flex justify-center items-center h-full px-4"
      >
        <img src={logo} alt="mebuki" className="h-6 w-auto opacity-90" />
      </div>

      {/* 右側：スペース（左側との対称性のため） */}
      <div className="w-20 h-full" />
    </header>
  )
}
