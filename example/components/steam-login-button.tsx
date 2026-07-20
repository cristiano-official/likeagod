import { cn } from '@/lib/utils'

export function SteamLoginButton({
  className,
  label = 'Sign in through Steam',
}: {
  className?: string
  label?: string
}) {
  return (
    <a
      href="/api/auth/steam"
      className={cn(
        'inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90',
        className,
      )}
    >
      {/* Steam mark */}
      <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden="true">
        <path d="M11.98 0C5.66 0 .48 4.88.02 11.08l6.43 2.66a3.38 3.38 0 0 1 1.9-.59l2.86-4.15v-.06a4.51 4.51 0 1 1 4.51 4.51h-.1l-4.09 2.92c0 .05.01.1.01.15a3.39 3.39 0 1 1-6.74-.56L.19 15.28A12 12 0 1 0 11.98 0zm-4.4 18.2 1.47.61a2.56 2.56 0 1 0 1.53-3.34l1.52.63a1.88 1.88 0 1 1-1.45 3.46l-3.07-1.36zm11.4-8.71a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0-4.73a1.73 1.73 0 1 1-1.73 1.73 1.73 1.73 0 0 1 1.73-1.73z" />
      </svg>
      {label}
    </a>
  )
}
