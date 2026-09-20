import Link from "next/link";

import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <Card>
      <EmptyState
        title="Page not found"
        description="The page you are looking for does not exist."
        action={
          <Link href="/" className={buttonVariants()}>
            Back to dashboard
          </Link>
        }
      />
    </Card>
  );
}
