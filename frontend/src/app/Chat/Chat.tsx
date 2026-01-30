import * as React from 'react';
import {
  Dropdown,
  DropdownItem,
  DropdownList,
  MenuToggle,
  MenuToggleElement,
  PageSection,
} from '@patternfly/react-core';
import {
  Chatbot,
  ChatbotContent,
  ChatbotDisplayMode,
  ChatbotFooter,
  ChatbotFootnote,
  ChatbotHeader,
  ChatbotHeaderMain,
  ChatbotHeaderMenu,
  ChatbotHeaderTitle,
  ChatbotHeaderActions,
  ChatbotConversationHistoryNav,
  ChatbotWelcomePrompt,
  Message,
  MessageBar,
  MessageBox,
  MessageProps,
  Conversation,
} from '@patternfly/chatbot';

import { ChatAPI, Chat as ChatType, ChatMessage, StreamingEvent, Flow } from './chatApi';
import userAvatar from '@app/images/user-avatar.svg';
import aiLogo from '@app/images/ai-logo-transparent.svg';

import '@patternfly/chatbot/dist/css/main.css';

const Chat: React.FunctionComponent = () => {
  // Chat list state
  const [chats, setChats] = React.useState<ChatType[]>([]);
  const [selectedChatId, setSelectedChatId] = React.useState<number | null>(null);
  const [chatsLoading, setChatsLoading] = React.useState(true);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);

  // Flow selector state
  const [flows, setFlows] = React.useState<Flow[]>([]);
  const [selectedFlowId, setSelectedFlowId] = React.useState<string | null>(null);
  const [isFlowMenuOpen, setIsFlowMenuOpen] = React.useState(false);

  // Messages state
  const [messages, setMessages] = React.useState<MessageProps[]>([]);
  const [messagesLoading, setMessagesLoading] = React.useState(false);
  const [isSending, setIsSending] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState<string>();

  const historyRef = React.useRef<HTMLButtonElement>(null);
  const displayMode = ChatbotDisplayMode.embedded;

  // Load chats and flows on mount
  React.useEffect(() => {
    loadChats();
    loadFlows();
  }, []);

  const loadFlows = async () => {
    try {
      const response = await ChatAPI.getFlows();
      const flowData = response?.data || [];
      setFlows(flowData);
      if (flowData.length > 0 && !selectedFlowId) {
        setSelectedFlowId(flowData[0].id);
      }
    } catch (err) {
      console.error('Failed to load flows:', err);
      setFlows([]);
    }
  };

  // Load messages when chat changes
  React.useEffect(() => {
    if (selectedChatId) {
      loadMessages(selectedChatId);
    } else {
      setMessages([]);
    }
  }, [selectedChatId]);

  const loadChats = async () => {
    setChatsLoading(true);
    try {
      const response = await ChatAPI.getChats();
      const chatData = response?.data || [];
      setChats(chatData);
      if (chatData.length > 0 && !selectedChatId) {
        setSelectedChatId(chatData[0].id);
      }
    } catch (err) {
      console.error('Failed to load chats:', err);
      setChats([]);
    } finally {
      setChatsLoading(false);
    }
  };

  const loadMessages = async (chatId: number) => {
    setMessagesLoading(true);
    try {
      const response = await ChatAPI.getMessages(chatId);
      const messageData = response?.data || [];
      const messageProps: MessageProps[] = messageData.map((msg: ChatMessage) => ({
        id: msg.id.toString(),
        role: msg.role === 'user' ? 'user' : 'bot',
        content: msg.content,
        name: msg.role === 'user' ? 'You' : 'Assistant',
        avatar: msg.role === 'user' ? userAvatar : aiLogo,
        timestamp: new Date(msg.created_at).toLocaleString(),
        avatarProps: msg.role === 'user' ? { isBordered: true } : undefined,
      }));
      setMessages(messageProps);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setMessages([]);
    } finally {
      setMessagesLoading(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const newChat = await ChatAPI.createChat({ title: 'New Chat' });
      setChats((prev) => [newChat, ...prev]);
      setSelectedChatId(newChat.id);
      setMessages([]);
      setIsDrawerOpen(false);
    } catch (err) {
      console.error('Failed to create chat:', err);
    }
  };

  const handleSelectConversation = (
    _e: React.MouseEvent | undefined,
    itemId: string | number | undefined
  ) => {
    if (itemId) {
      setSelectedChatId(Number(itemId));
      setIsDrawerOpen(false);
    }
  };

  const handleSend = (message: string | number) => {
    const messageText = typeof message === 'string' ? message : message.toString();
    if (!messageText.trim() || !selectedChatId || isSending) return;

    setIsSending(true);
    const timestamp = new Date().toLocaleString();

    // Add user message immediately
    const userMessage: MessageProps = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      name: 'You',
      avatar: userAvatar,
      timestamp,
      avatarProps: { isBordered: true },
    };

    // Add loading bot message
    const loadingBotMessage: MessageProps = {
      id: `bot-${Date.now()}`,
      role: 'bot',
      content: '',
      name: 'Assistant',
      avatar: aiLogo,
      timestamp,
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingBotMessage]);
    setAnnouncement(`Message from You: ${messageText}. Assistant is thinking...`);

    let accumulatedContent = '';

    ChatAPI.createStreamingMessage(
      selectedChatId,
      messageText,
      (event: StreamingEvent) => {
        if (event.type === 'content' && event.content) {
          accumulatedContent += event.content;
          // Update the bot message with accumulated content
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === loadingBotMessage.id
                ? { ...msg, content: accumulatedContent, isLoading: false }
                : msg
            )
          );
        } else if (event.type === 'done') {
          // Reload to get the saved message IDs
          loadMessages(selectedChatId);
          setIsSending(false);
          setAnnouncement(`Assistant: ${accumulatedContent}`);

          // Update chat title if first message
          if (messages.length === 0) {
            const title = messageText.slice(0, 50) + (messageText.length > 50 ? '...' : '');
            ChatAPI.updateChat(selectedChatId, { title }).then(() => loadChats());
          }
        } else if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === loadingBotMessage.id
                ? { ...msg, content: 'Sorry, an error occurred.', isLoading: false }
                : msg
            )
          );
          setIsSending(false);
        }
      },
      (err) => {
        console.error('Streaming error:', err);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingBotMessage.id
              ? { ...msg, content: 'Sorry, an error occurred.', isLoading: false }
              : msg
          )
        );
        setIsSending(false);
      },
      () => {
        setIsSending(false);
      },
      selectedFlowId || undefined
    );
  };

  // Build conversations for the drawer
  const conversations: Conversation[] = chats.map((chat) => ({
    id: chat.id.toString(),
    text: chat.title,
  }));

  const welcomePrompts = [
    {
      title: 'Research a topic',
      message: 'Help me research and summarize information about a specific topic.',
      onClick: () => handleSend('Help me research and summarize information about a specific topic.'),
    },
    {
      title: 'Analyze data',
      message: 'Help me analyze and interpret data or documents.',
      onClick: () => handleSend('Help me analyze and interpret data or documents.'),
    },
  ];

  return (
    <PageSection isFilled hasBodyWrapper={false} style={{ height: '100%', padding: 0 }}>
      <Chatbot displayMode={displayMode}>
        <ChatbotConversationHistoryNav
          displayMode={displayMode}
          onDrawerToggle={() => setIsDrawerOpen(!isDrawerOpen)}
          isDrawerOpen={isDrawerOpen}
          setIsDrawerOpen={setIsDrawerOpen}
          activeItemId={selectedChatId?.toString()}
          onSelectActiveItem={handleSelectConversation}
          conversations={conversations}
          onNewChat={handleNewChat}
          isLoading={chatsLoading}
          drawerContent={
            <>
              <ChatbotHeader>
                <ChatbotHeaderMain>
                  <ChatbotHeaderMenu
                    ref={historyRef}
                    aria-expanded={isDrawerOpen}
                    onMenuToggle={() => setIsDrawerOpen(!isDrawerOpen)}
                  />
                  <ChatbotHeaderTitle>
                    {selectedChatId
                      ? chats.find((c) => c.id === selectedChatId)?.title || 'Chat'
                      : 'Research Assistant'}
                  </ChatbotHeaderTitle>
                </ChatbotHeaderMain>
                <ChatbotHeaderActions>
                  <Dropdown
                    isOpen={isFlowMenuOpen}
                    onOpenChange={(isOpen) => setIsFlowMenuOpen(isOpen)}
                    onSelect={() => setIsFlowMenuOpen(false)}
                    toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
                      <MenuToggle
                        ref={toggleRef}
                        onClick={() => setIsFlowMenuOpen(!isFlowMenuOpen)}
                        isExpanded={isFlowMenuOpen}
                        isDisabled={flows.length === 0}
                      >
                        {flows.find((f) => f.id === selectedFlowId)?.name || 'Select Flow'}
                      </MenuToggle>
                    )}
                  >
                    <DropdownList>
                      {flows.map((flow) => (
                        <DropdownItem
                          key={flow.id}
                          onClick={() => setSelectedFlowId(flow.id)}
                          description={flow.description}
                        >
                          {flow.name}
                        </DropdownItem>
                      ))}
                    </DropdownList>
                  </Dropdown>
                </ChatbotHeaderActions>
              </ChatbotHeader>
              <ChatbotContent>
                <MessageBox announcement={announcement}>
                  {messages.length === 0 && !messagesLoading && (
                    <ChatbotWelcomePrompt
                      title="Hello!"
                      description="How can I help you today?"
                      prompts={welcomePrompts}
                    />
                  )}
                  {messages.map((message) => (
                    <Message
                      key={message.id}
                      {...message}
                      actions={
                        message.role === 'bot' && !message.isLoading
                          ? {
                              copy: {
                                onClick: () => navigator.clipboard.writeText(message.content || ''),
                              },
                            }
                          : undefined
                      }
                    />
                  ))}
                </MessageBox>
              </ChatbotContent>
              <ChatbotFooter>
                <MessageBar
                  onSendMessage={handleSend}
                  isSendButtonDisabled={isSending || !selectedChatId}
                  hasStopButton={isSending}
                  handleStopButton={() => setIsSending(false)}
                />
                <ChatbotFootnote label="AI-powered research assistant. Verify important information." />
              </ChatbotFooter>
            </>
          }
        />
      </Chatbot>
    </PageSection>
  );
};

export { Chat };
