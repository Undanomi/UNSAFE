import "server-only"

import { Filter } from "firebase-admin/firestore"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import {
  type MachineListItem,
  type MachineListQuery,
  selectMachinePage,
} from "@/lib/machines/list-query"
import type { MachinesDocument, UsersDocument } from "@/types/firestore"

const visibleStatuses = [
  "created",
  "building",
  "ready",
  "failed",
  "cancelled",
  "preparing",
] as const

export async function getMachineListService(viewerUserId: string, query: MachineListQuery) {
  const firestore = getFirebaseAdminFirestore()
  // Only authorized, non-secret list metadata is read. Filtering/paging stays on the server.
  const [snapshot, viewer] = await Promise.all([
    firestore
      .collection("machines")
      .where(
        Filter.and(
          Filter.where("status", "in", visibleStatuses),
          query.owned
            ? Filter.or(
                Filter.where("created_by", "==", `users/${viewerUserId}`),
                Filter.where("created_by", "==", viewerUserId),
              )
            : Filter.or(
                Filter.where("published", "==", true),
                Filter.where("created_by", "==", `users/${viewerUserId}`),
                Filter.where("created_by", "==", viewerUserId),
              ),
        ),
      )
      .select(
        "name",
        "summary",
        "description",
        "tags",
        "level",
        "created_at",
        "created_by",
        "published",
        "status",
      )
      .get(),
    firestore.collection("users").doc(viewerUserId).get(),
  ])
  const solved = new Set((viewer.data() as UsersDocument | undefined)?.solved_machines ?? [])
  const items: MachineListItem[] = snapshot.docs.map((doc) => {
    const machine = doc.data() as MachinesDocument
    const authorId = machine.created_by.replace(/^users\//, "")
    return {
      id: doc.id,
      name: machine.name,
      summary: machine.summary,
      description: machine.description,
      tags: machine.tags ?? [],
      level: machine.level,
      created_at: machine.created_at,
      published: machine.published,
      status: machine.status,
      authorId,
      author: "ユーザー",
      isOwned: authorId === viewerUserId,
      isSolved: solved.has(`machines/${doc.id}`),
    }
  })
  const result = selectMachinePage(items, query)
  const authorIds = [...new Set(result.machines.map((machine) => machine.authorId))]
  if (authorIds.length) {
    const authors = await firestore.getAll(
      ...authorIds.map((id) => firestore.collection("users").doc(id)),
    )
    const names = new Map(
      authors.map((author) => [author.id, author.data()?.name as string | undefined]),
    )
    result.machines = result.machines.map((machine) => ({
      ...machine,
      author: names.get(machine.authorId) || "ユーザー",
    }))
  }
  return result
}
