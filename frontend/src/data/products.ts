export type Product = {
  id: string;
  name: string;
  description: string;
  tag: string;
  price: number;
};

export const PRODUCTS: Product[] = [
  {
    id: "nx-monitor",
    name: "Signal Monitor",
    description: "A compact desk display for cluster health at a glance.",
    tag: "Ops gear",
    price: 49.0,
  },
  {
    id: "nx-notebook",
    name: "Incident Notebook",
    description: "Ruled pages for RCA notes, timelines, and approvals.",
    tag: "Field kit",
    price: 18.5,
  },
  {
    id: "nx-mug",
    name: "On-Call Mug",
    description: "Ceramic mug for long remediation nights.",
    tag: "Everyday",
    price: 14.0,
  },
  {
    id: "nx-patch",
    name: "Self-Heal Patch",
    description: "Embroidered patch celebrating recovered services.",
    tag: "Merch",
    price: 9.0,
  },
];
