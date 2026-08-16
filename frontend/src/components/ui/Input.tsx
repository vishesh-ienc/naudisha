import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: ReactNode
  error?: string | null
  success?: string | null
  leadingIcon?: ReactNode
  trailing?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, success, leadingIcon, trailing, id, ...props }, ref) => {
    const generatedId = useId()
    const inputId = id ?? generatedId
    const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="mb-1.5 block text-xs font-medium text-muted-foreground">
            {label}
          </label>
        )}

        <div className="relative">
          {leadingIcon && (
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {leadingIcon}
            </span>
          )}

          <input
            ref={ref}
            id={inputId}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              'h-11 w-full rounded-lg border bg-background px-3 text-sm transition-colors',
              'placeholder:text-muted-foreground/60',
              'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--ring)]',
              'disabled:cursor-not-allowed disabled:opacity-50',
              leadingIcon && 'pl-9',
              trailing && 'pr-24',
              error
                ? 'border-destructive focus-visible:outline-destructive'
                : success
                  ? 'border-[var(--success)]'
                  : 'border-[var(--input)]',
              className,
            )}
            {...props}
          />

          {trailing && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2">{trailing}</span>
          )}
        </div>

        {error ? (
          <p id={`${inputId}-error`} role="alert" className="mt-1.5 flex items-start gap-1.5 text-xs text-destructive">
            <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>{error}</span>
          </p>
        ) : success ? (
          <p className="mt-1.5 flex items-start gap-1.5 text-xs text-[var(--success)]">
            <CheckCircle2 className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>{success}</span>
          </p>
        ) : hint ? (
          <p id={`${inputId}-hint`} className="mt-1.5 text-xs text-muted-foreground">
            {hint}
          </p>
        ) : null}
      </div>
    )
  },
)
Input.displayName = 'Input'
