export function SettingsSection({ children, className = "" }) {
  return <section className={`settings-section ${className}`.trim()}>{children}</section>;
}

export function SettingsCard({ as: Component = "section", children, className = "", ...props }) {
  return <Component className={`panel settings-card ${className}`.trim()} {...props}>{children}</Component>;
}

export function SettingsGrid({ children, className = "" }) {
  return <div className={`settings-grid ${className}`.trim()}>{children}</div>;
}

export function SettingsTableWrapper({ children, className = "" }) {
  return <div className={`table-wrap settings-table-wrapper ${className}`.trim()}>{children}</div>;
}
