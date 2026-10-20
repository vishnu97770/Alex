import { useMeQuery } from '../../api/api'

// The signed-in user's uid, or null (signed out, or the session check has not answered yet).
export function useSignedInUid() {
  const { currentData } = useMeQuery()

  return currentData?.uid ?? null
}
