// Minimal className joiner -- avoids adding the `clsx` package as a
// dependency for something this small.
export default function clsx(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

