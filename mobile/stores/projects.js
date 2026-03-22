import { create } from "zustand";
import { fetchProjects } from "../lib/api";

const useProjectStore = create((set) => ({
  projects: [],
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null });
    try {
      const data = await fetchProjects();
      set({ projects: Array.isArray(data) ? data : [], loading: false });
    } catch (e) {
      set({ error: e.message, loading: false });
    }
  },
}));

export default useProjectStore;
