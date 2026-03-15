export const router = {
  replace: jest.fn(),
  push: jest.fn(),
  back: jest.fn(),
};

export const Stack = ({ children }) => children;
export const Tabs = ({ children }) => children;
export const Slot = () => null;

export const useRouter = jest.fn(() => router);
export const useSegments = jest.fn(() => []);
export const usePathname = jest.fn(() => "/");
