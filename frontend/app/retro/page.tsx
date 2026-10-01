import { RetroBoard } from "@/components/retro/retro-board";
import { UserActionBoard } from "@/components/retro/user-action-board";

export default function RetroPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <UserActionBoard />
      <RetroBoard />
    </div>
  );
}
