import { create } from "zustand";
import { fetchPage, updatePage, createPage } from "../lib/api";

const usePageStore = create((set) => ({
  currentPage: null,
  loading: false,
  saving: false,
  error: null,

  fetchPage: async (id) => {
    set({ currentPage: null, loading: true, error: null });
    try {
      const page = await fetchPage(id);
      set({ currentPage: page, loading: false });
    } catch (e) {
      set({ currentPage: null, error: e.message, loading: false });
    }
  },

  updatePage: async (id, data) => {
    set({ saving: true, error: null });
    try {
      const page = await updatePage(id, data);
      set({ currentPage: page, saving: false });
      return page;
    } catch (e) {
      set({ error: e.message, saving: false });
      throw e;
    }
  },

  createPage: async (projectId, title) => {
    set({ saving: true, error: null });
    try {
      const page = await createPage(projectId, title);
      set({ saving: false });
      return page;
    } catch (e) {
      set({ error: e.message, saving: false });
      throw e;
    }
  },

  clearPage: () => set({ currentPage: null, error: null }),
}));

export default usePageStore;
