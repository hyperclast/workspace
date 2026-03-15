let counter = 0;

export const randomUUID = jest.fn(() => `test-uuid-${++counter}`);

export const __reset = () => {
  counter = 0;
  randomUUID.mockClear();
};
