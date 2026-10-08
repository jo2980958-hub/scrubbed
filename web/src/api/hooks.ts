import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { CasePatch, NewCaseInput, NewStaffInput, PageInput } from './types';

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: api.me, staleTime: 60_000 });

export const useCases = (day: string) =>
  useQuery({ queryKey: ['cases', day], queryFn: () => api.listCases(day), refetchInterval: 30_000 });

export const useCase = (id: string) =>
  useQuery({ queryKey: ['case', id], queryFn: () => api.getCase(id), refetchInterval: 30_000 });

export const usePages = (id: string) =>
  useQuery({ queryKey: ['pages', id], queryFn: () => api.pages(id), refetchInterval: 20_000 });

export const useConversations = (id: string) =>
  useQuery({ queryKey: ['conversations', id], queryFn: () => api.conversations(id), refetchInterval: 20_000 });

export const useForms = (id: string) =>
  useQuery({ queryKey: ['forms', id], queryFn: () => api.forms(id), refetchInterval: 30_000 });

export const useFollowups = () =>
  useQuery({ queryKey: ['followups'], queryFn: api.followups, refetchInterval: 30_000 });

export const useStaff = () => useQuery({ queryKey: ['staff'], queryFn: api.listStaff, staleTime: 60_000 });

function useRefreshCases() {
  const qc = useQueryClient();
  return (day?: string) => {
    qc.invalidateQueries({ queryKey: ['cases'] });
    if (day) qc.invalidateQueries({ queryKey: ['cases', day] });
  };
}

export function useCreateCase(day: string) {
  const refresh = useRefreshCases();
  return useMutation({ mutationFn: (i: NewCaseInput) => api.createCase(i), onSuccess: () => refresh(day) });
}

export function usePatchCase(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: CasePatch) => api.patchCase(id, p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases'] });
      qc.invalidateQueries({ queryKey: ['case', id] });
    },
  });
}

export function useSendPage(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PageInput) => api.sendPage(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pages', id] }),
  });
}

export function useAddStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (i: NewStaffInput) => api.addStaff(i),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff'] }),
  });
}
