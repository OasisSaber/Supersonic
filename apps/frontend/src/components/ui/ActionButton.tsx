import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { classNames } from '../../lib/classNames'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode
  pending?: boolean
  variant?: ButtonVariant
}

export function ActionButton({
  children,
  className,
  disabled,
  icon,
  pending = false,
  type = 'button',
  variant = 'secondary',
  ...props
}: ActionButtonProps) {
  return (
    <button
      {...props}
      aria-busy={pending || undefined}
      className={classNames('sp-button', `sp-button--${variant}`, className)}
      disabled={disabled || pending}
      type={type}
    >
      {(pending || icon) && (
        <span className="sp-button__icon" aria-hidden="true">
          {pending ? <span className="sp-spinner" /> : icon}
        </span>
      )}
      <span>{children}</span>
    </button>
  )
}
