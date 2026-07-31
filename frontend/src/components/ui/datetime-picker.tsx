import * as React from "react"
import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

/**
 * Value format: "YYYY-MM-DDTHH:mm" (datetime-local compatible)
 */
interface DateTimePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  buttonSize?: React.ComponentProps<typeof Button>["size"]
  buttonStyle?: React.CSSProperties
  placeholderStyle?: React.CSSProperties
  calendarClassNames?: React.ComponentProps<typeof Calendar>["classNames"]
  timeInputClassName?: string
  timeInputStyle?: React.CSSProperties
  showTime?: boolean
}

function toDate(datetimeLocal: string): Date | undefined {
  if (!datetimeLocal) return undefined
  const d = new Date(datetimeLocal)
  return isNaN(d.getTime()) ? undefined : d
}

function toDatetimeLocal(date: Date, time: string): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  const dateStr = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${dateStr}T${time || "00:00"}`
}

function extractTime(datetimeLocal: string): string {
  if (!datetimeLocal) return ""
  const match = datetimeLocal.match(/T(\d{2}:\d{2})/)
  return match ? match[1] : ""
}

function DateTimePicker({
  value,
  onChange,
  placeholder = "Pick date & time",
  className,
  buttonSize,
  buttonStyle,
  placeholderStyle,
  calendarClassNames,
  timeInputClassName,
  timeInputStyle,
  showTime = true,
}: DateTimePickerProps) {
  const [open, setOpen] = React.useState(false)
  const selectedDate = toDate(value)
  const timeValue = extractTime(value)

  const handleDateSelect = (date: Date | undefined) => {
    if (!date) return
    const time = timeValue || "00:00"
    onChange(toDatetimeLocal(date, time))
    if (!showTime) setOpen(false)
  }

  const handleTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = e.target.value
    if (selectedDate) {
      onChange(toDatetimeLocal(selectedDate, newTime))
    } else {
      // If no date selected yet, use today
      onChange(toDatetimeLocal(new Date(), newTime))
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size={buttonSize}
          style={buttonStyle}
          className={cn(
            "w-full justify-start font-normal",
            !value && "text-[var(--text-faint)]",
            className
          )}
        >
          <CalendarIcon />
          {selectedDate
            ? format(selectedDate, showTime ? "yyyy/MM/dd HH:mm" : "yyyy/MM/dd")
            : <span style={placeholderStyle}>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleDateSelect}
          defaultMonth={selectedDate}
          classNames={calendarClassNames}
        />
        {showTime && (
          <div className="border-t border-border px-3 py-2">
            <Input
              type="time"
              value={timeValue}
              onChange={handleTimeChange}
              style={timeInputStyle}
              className={cn("h-8", timeInputClassName)}
            />
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}

export { DateTimePicker }
