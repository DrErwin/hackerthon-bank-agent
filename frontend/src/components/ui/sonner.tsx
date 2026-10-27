"use client"

import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {

  return (
    <Sonner
      theme="light"
      position="top-center"
      duration={6000}
      closeButton
      containerAriaLabel="提示"
      toastOptions={{ style: { fontSize: "1rem", fontFamily: "var(--ds-font)" }, closeButtonAriaLabel: "关闭提示" }}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon aria-hidden="true" className="size-6" />,
        info: <InfoIcon aria-hidden="true" className="size-6" />,
        warning: <TriangleAlertIcon aria-hidden="true" className="size-6" />,
        error: <OctagonXIcon aria-hidden="true" className="size-6" />,
        loading: <Loader2Icon aria-hidden="true" className="size-6 animate-spin" />,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
