"use client"

import { useRouter } from "next/navigation"
import type { MouseEvent } from "react"

export function MachineFilterResetButton() {
  const router = useRouter()

  function resetFilters(event: MouseEvent<HTMLButtonElement>) {
    const form = event.currentTarget.form
    if (!form) return

    const keyword = form.elements.namedItem("q")
    if (keyword instanceof HTMLInputElement) keyword.value = ""

    form
      .querySelectorAll<HTMLInputElement>('input[name="level"], input[name="owned"]')
      .forEach((input) => {
        input.checked = false
      })

    const solved = form.elements.namedItem("solved")
    if (solved instanceof HTMLSelectElement) solved.value = ""

    const sort = form.elements.namedItem("sort")
    if (sort instanceof HTMLSelectElement) sort.value = "desc"

    router.replace("/machines", { scroll: false })
  }

  return (
    <button
      className="cursor-pointer p-2 text-sm text-[#a8b5cc] underline underline-offset-4"
      onClick={resetFilters}
      type="button"
    >
      条件をリセット
    </button>
  )
}
