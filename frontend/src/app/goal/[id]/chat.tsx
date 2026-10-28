import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { revisionArrived, useChat, useDecideRevision, useGoal, useMarkRead, useSendMessage } from '@/api/hooks';
import type { ChatMessage } from '@/api/types';
import { useI18n } from '@/i18n/I18nContext';
import { textDir } from '@/lib/text';
import { AppText, Badge, Button, Row } from '@/ui';
import { MAX_WIDTH, radius, space, useColors } from '@/ui/theme';

function MessageBubble({ msg, goalId }: { msg: ChatMessage; goalId: number }) {
  const { t } = useI18n();
  const c = useColors();
  const decide = useDecideRevision(goalId);
  const mine = msg.role === 'user';
  const label =
    msg.kind === 'checkin'
      ? t('checkinLabel')
      : msg.kind === 'revision_applied'
        ? t('planUpdatedLabel')
        : msg.kind === 'revision_proposal'
          ? t('proposalLabel')
          : null;
  const bg = mine ? c.userBubble : msg.kind === 'safety' ? c.dangerSoft : msg.kind === 'revision_proposal' ? c.warningSoft : c.botBubble;
  const decision = msg.meta.decision;

  return (
    <View style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '85%', marginBottom: space.sm }}>
      {label ? (
        <View style={{ marginBottom: 3 }}>
          <Badge text={label} tone={msg.kind === 'revision_proposal' ? 'warning' : msg.kind === 'checkin' ? 'primary' : 'success'} />
        </View>
      ) : null}
      <View
        style={{
          backgroundColor: bg,
          borderRadius: radius.lg,
          borderWidth: mine ? 0 : 1,
          borderColor: c.border,
          paddingVertical: 9,
          paddingHorizontal: 13,
        }}>
        <AppText style={[{ color: mine ? c.userBubbleText : c.text }, textDir(msg.content)]}>{msg.content}</AppText>
        {msg.kind === 'revision_proposal' && msg.meta.revision_id ? (
          decision ? (
            <AppText muted size={12} style={{ marginTop: space.xs }}>
              {decision === 'approved' ? t('approved') : t('rejected')}
            </AppText>
          ) : (
            <Row style={{ marginTop: space.sm }}>
              <Button title={t('approve')} small loading={decide.isPending}
                onPress={() => decide.mutate({ revisionId: msg.meta.revision_id!, approve: true })} />
              <Button title={t('reject')} small variant="secondary" disabled={decide.isPending}
                onPress={() => decide.mutate({ revisionId: msg.meta.revision_id!, approve: false })} />
            </Row>
          )
        ) : null}
      </View>
    </View>
  );
}

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goalId = Number(id);
  const { t } = useI18n();
  const c = useColors();
  const goal = useGoal(goalId);
  // Id of the reply after which a plan revision is expected (it is prepared in the background).
  const [waitAfterId, setWaitAfterId] = useState<number | null>(null);
  const chat = useChat(goalId, waitAfterId);
  const send = useSendMessage(goalId);
  const markRead = useMarkRead();
  const [text, setText] = useState('');
  const list = useRef<FlatList<ChatMessage>>(null);
  const messages = useMemo(() => chat.data ?? [], [chat.data]);
  const waitingForRevision = waitAfterId !== null && !revisionArrived(messages, waitAfterId);
  const lastId = messages.at(-1)?.id;

  useEffect(() => {
    markRead.mutate({ goalId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goalId, lastId]);

  // Give up waiting for a revision after 30 s.
  useEffect(() => {
    if (waitAfterId === null) return;
    const timer = setTimeout(() => setWaitAfterId(null), 30_000);
    return () => clearTimeout(timer);
  }, [waitAfterId]);

  const submit = () => {
    const content = text.trim();
    if (!content || send.isPending) return;
    setText('');
    send.mutate(content, { onSuccess: (out) => out.revision_in_progress && setWaitAfterId(out.reply.id) });
  };

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen options={{ title: goal.data ? `${t('chat')} · ${goal.data.title}` : t('chat') }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        <FlatList
          ref={list}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          renderItem={({ item }) => <MessageBubble msg={item} goalId={goalId} />}
          contentContainerStyle={{ padding: space.lg, width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center' }}
          onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
          ListFooterComponent={
            send.isPending ? (
              <AppText muted size={13}>{t('coachTyping')}</AppText>
            ) : waitingForRevision ? (
              <AppText muted size={13}>{t('preparingUpdate')}</AppText>
            ) : undefined
          }
        />
        {send.error ? <AppText style={{ color: c.danger, paddingHorizontal: space.lg }}>{send.error.message}</AppText> : null}
        <View style={{ borderTopWidth: 1, borderTopColor: c.border, backgroundColor: c.card }}>
          <Row style={{ padding: space.sm, width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center' }}>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder={t('chatPh')}
              placeholderTextColor={c.muted}
              multiline
              onKeyPress={(e) => {
                // Enter sends on web; Shift+Enter makes a new line.
                const ne = e.nativeEvent as unknown as { key: string; shiftKey?: boolean };
                if (Platform.OS === 'web' && ne.key === 'Enter' && !ne.shiftKey) {
                  (e as unknown as { preventDefault: () => void }).preventDefault();
                  submit();
                }
              }}
              style={[
                {
                  flex: 1,
                  maxHeight: 120,
                  borderWidth: 1,
                  borderColor: c.border,
                  borderRadius: radius.md,
                  paddingHorizontal: 12,
                  paddingVertical: 9,
                  color: c.text,
                  fontSize: 15,
                },
                textDir(text || t('chatPh')),
              ]}
            />
            <Button title={t('send')} onPress={submit} disabled={!text.trim()} loading={send.isPending} />
          </Row>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
