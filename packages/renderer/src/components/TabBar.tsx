import { Settings } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface TabBarProps {
  onSettingsClick: () => void
}

export function TabBar({ onSettingsClick }: TabBarProps) {
  return (
    <aside className="fixed right-0 top-0 h-screen w-14 z-40 flex flex-col items-center py-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={onSettingsClick}
        className="text-foreground-muted hover:text-foreground"
      >
        <Settings className="w-5 h-5" />
        <span className="sr-only">設定</span>
      </Button>
    </aside>
  )
}
