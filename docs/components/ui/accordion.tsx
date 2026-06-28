import * as React from 'react'

import { cn } from '@/lib/utils'

type AccordionProps = React.HTMLAttributes<HTMLDivElement> & {
  type?: 'single'
  collapsible?: boolean
}

export function Accordion({ className, ...props }: AccordionProps) {
  return <div className={cn('divide-y divide-studio-line', className)} {...props} />
}

type AccordionItemProps = React.HTMLAttributes<HTMLDivElement> & {
  value?: string
}

export function AccordionItem({ className, value: _value, ...props }: AccordionItemProps) {
  return <div className={cn('py-4', className)} {...props} />
}

export function AccordionTrigger({ className, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn('flex w-full items-center justify-between text-left font-semibold', className)}
      type="button"
      {...props}
    >
      {children}
    </button>
  )
}

export function AccordionContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('pt-3 text-sm text-studio-muted', className)} {...props} />
}
