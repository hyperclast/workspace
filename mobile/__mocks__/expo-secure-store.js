const store = new Map();

export const getItemAsync = jest.fn((key) => Promise.resolve(store.get(key) ?? null));
export const setItemAsync = jest.fn((key, value) => {
  store.set(key, value);
  return Promise.resolve();
});
export const deleteItemAsync = jest.fn((key) => {
  store.delete(key);
  return Promise.resolve();
});

export const __reset = () => {
  store.clear();
  getItemAsync.mockClear();
  setItemAsync.mockClear();
  deleteItemAsync.mockClear();
};
