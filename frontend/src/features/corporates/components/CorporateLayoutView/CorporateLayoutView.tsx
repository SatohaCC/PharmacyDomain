import type { ReactNode } from "react";
import type { Corporate } from "../../model/corporate";
import { Tabs } from "../../../../shared/ui/Tabs";
import { Title, Heading, Paragraph } from "../../../../shared/ui/Elements";
import { Link } from "../../../../shared/ui/Link";

export function CorporateLayoutView({
  corporate: c,
  children,
}: {
  corporate: Corporate;
  children: ReactNode;
}) {
  return (
    <>
      <Title>
        <div>
          <Heading>{c.name}</Heading>
          <Paragraph>
            代表者 {c.representative_name} · {c.is_active ? "有効" : "停止中"}
          </Paragraph>
        </div>
      </Title>
      <Tabs aria-label="法人管理">
        <Link href={`/admin/corporates/${encodeURIComponent(c.id)}`}>概要</Link>
        <Link href={`/admin/corporates/${encodeURIComponent(c.id)}/stores`}>
          店舗
        </Link>
        <Link href={`/admin/corporates/${encodeURIComponent(c.id)}/users`}>
          ユーザー
        </Link>
      </Tabs>
      {children}
    </>
  );
}
