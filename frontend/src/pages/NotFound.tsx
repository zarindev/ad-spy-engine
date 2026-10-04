import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <EmptyState
      icon={Compass}
      title="Page not found"
      description="That page doesn't exist."
      action={<Button asChild><Link to="/">Back to dashboard</Link></Button>}
    />
  );
}
