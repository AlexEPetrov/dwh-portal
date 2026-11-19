import { QueryClient } from '@tanstack/react-query';

/** Host-owned cache. All current application queries contain private server data. */
export const queryClient = new QueryClient();

/** Cancellation runs synchronously before removal; late responses cannot repopulate removed queries. */
export function clearPrivateQueryData(): void {
    void queryClient.cancelQueries();
    queryClient.removeQueries();
    queryClient.getMutationCache().clear();
}
