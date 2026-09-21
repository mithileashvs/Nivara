export function Card({ as: Tag = 'div', className = '', children, ...props }) {
  return (
    <Tag className={`card ${className}`} {...props}>
      {children}
    </Tag>
  )
}

export function CardHeader({ title, description, action, className = '' }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4 ${className}`}>
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-forest-700">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function CardBody({ className = '', children }) {
  return <div className={`p-5 ${className}`}>{children}</div>
}
