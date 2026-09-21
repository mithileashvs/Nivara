/** Nivara mark: a four-leaf medical/botanical cross, as in the design reference. */
export function LogoMark({ size = 28, className = '' }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} className={className} aria-hidden="true" fill="none">
      <path
        d="M16 3.5c2.6 2.4 4 5.1 4 7.8 0 1.6-.5 3-1.4 4.2 1.4-.6 2.9-.9 4.4-.9 2.7 0 5 .9 7 2.6-2.3 2.5-5 3.8-7.8 3.8-1.6 0-3-.4-4.2-1.2.7 1.5 1 3 1 4.6 0 2.7-1.1 5.2-3 7.1-1.9-1.9-3-4.4-3-7.1 0-1.6.3-3.1 1-4.6-1.2.8-2.6 1.2-4.2 1.2-2.8 0-5.5-1.3-7.8-3.8 2-1.7 4.3-2.6 7-2.6 1.5 0 3 .3 4.4.9-.9-1.2-1.4-2.6-1.4-4.2 0-2.7 1.4-5.4 4-7.8Z"
        fill="currentColor"
      />
      <circle cx="16" cy="16" r="2.6" className="fill-canvas" />
    </svg>
  )
}

export function Logo({ size = 'md', tone = 'dark', className = '' }) {
  const dims = { sm: 22, md: 26, lg: 32 }[size]
  const text = { sm: 'text-lg', md: 'text-xl', lg: 'text-2xl' }[size]
  const colour = tone === 'light' ? 'text-canvas' : 'text-forest'
  return (
    <span className={`inline-flex items-center gap-2 ${colour} ${className}`}>
      <LogoMark size={dims} />
      <span className={`${text} font-bold tracking-tight`}>Nivara</span>
    </span>
  )
}
