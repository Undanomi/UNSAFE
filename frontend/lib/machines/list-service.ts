import "server-only"

import { FieldPath, Filter, type Firestore } from "firebase-admin/firestore"
import { getFirebaseAdminFirestore } from "@/lib/firebase/admin"
import {
  MACHINE_PAGE_SIZE,
  type MachineListItem,
  type MachineListQuery,
  type MachineListResult,
  selectMachinePage,
} from "@/lib/machines/list-query"
import type { MachinesDocument, UsersDocument } from "@/types/firestore"

const visibleStatuses = ["created", "building", "ready", "failed", "preparing"] satisfies Exclude<
  MachinesDocument["status"],
  "deleted"
>[]

async function getMachineListDocuments(
  firestore: Firestore,
  viewerUserId: string,
  query: MachineListQuery,
) {
  const ownedFilter = Filter.or(
    Filter.where("created_by", "==", `users/${viewerUserId}`),
    Filter.where("created_by", "==", viewerUserId),
  )
  const visibilityFilter = query.owned
    ? ownedFilter
    : Filter.or(Filter.where("published", "==", true), ownedFilter)
  const isFiltered = Boolean(query.q || query.level || query.solved || query.owned)
  // Equality filters allow creation-date ordering without a status inequality sort.
  const statusFilter = isFiltered
    ? Filter.where("status", "!=", "deleted")
    : Filter.where("status", "in", visibleStatuses)
  const machines = firestore
    .collection("machines")
    .where(Filter.and(statusFilter, visibilityFilter))
  const metadata = machines.select(
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
  if (isFiltered) return { snapshot: await metadata.get(), pagination: null }

  const ordered = metadata.orderBy("created_at", query.sort).orderBy(FieldPath.documentId(), "asc")
  const total = (await ordered.count().get()).data().count
  const pageCount = Math.max(1, Math.ceil(total / MACHINE_PAGE_SIZE))
  const page = Math.min(query.page, pageCount)
  const snapshot = await ordered
    .offset((page - 1) * MACHINE_PAGE_SIZE)
    .limit(MACHINE_PAGE_SIZE)
    .get()
  return { snapshot, pagination: { total, page, pageCount } }
}

export async function getMachineListService(viewerUserId: string, query: MachineListQuery) {
  const firestore = getFirebaseAdminFirestore()
  const [{ snapshot, pagination }, viewer] = await Promise.all([
    getMachineListDocuments(firestore, viewerUserId, query),
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
  const result: MachineListResult = pagination
    ? { ...pagination, machines: items }
    : selectMachinePage(items, query)
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
