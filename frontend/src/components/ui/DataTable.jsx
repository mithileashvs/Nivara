/**
 * A table on wide screens, a stack of cards on small ones — so a dense admin
 * list stays readable on a phone without the page scrolling sideways.
 *
 * columns: [{ key, header, render(row), className, hideOnMobile }]
 */
export function DataTable({ columns, rows, rowKey = (r) => r.id, caption, onRowClick }) {
  return (
    <>
      <div className="scroll-x hidden md:block">
        <table className="w-full min-w-[40rem] border-collapse text-left">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="border-b border-line">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={`whitespace-nowrap px-5 py-3 text-xs font-semibold text-ink-muted ${c.className || ''}`}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={`transition-colors hover:bg-forest-50/60 ${onRowClick ? 'cursor-pointer' : ''}`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c) => (
                  <td key={c.key} className={`px-5 py-3.5 align-middle text-sm ${c.className || ''}`}>
                    {c.render ? c.render(row) : row[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-line md:hidden">
        {rows.map((row) => (
          <li key={rowKey(row)} className="px-4 py-4">
            <dl className="space-y-2">
              {columns
                .filter((c) => !c.hideOnMobile)
                .map((c) => (
                  <div key={c.key} className="flex items-start justify-between gap-4">
                    <dt className="shrink-0 text-xs font-medium text-ink-muted">{c.header}</dt>
                    <dd className="min-w-0 text-right text-sm text-ink">
                      {c.render ? c.render(row) : row[c.key]}
                    </dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  )
}
